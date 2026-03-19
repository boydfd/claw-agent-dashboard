# backend/app/services/session_indexer.py
"""Session indexer — ES sync background task and search interface."""
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from ..config import ES_URL, ES_INDEX_PREFIX, ES_SYNC_INTERVAL, SESSION_DATA_DIR
from ..services.scanner import list_agents

_es_client = None


async def _get_es():
    """Lazy-init ES async client."""
    global _es_client
    if _es_client is None and ES_URL:
        from elasticsearch import AsyncElasticsearch
        _es_client = AsyncElasticsearch(ES_URL)
    return _es_client


async def is_es_available() -> bool:
    """Check if ES is configured and reachable."""
    if not ES_URL:
        return False
    try:
        es = await _get_es()
        return await es.ping()
    except Exception:
        return False


async def close_es():
    """Close ES client."""
    global _es_client
    if _es_client:
        await _es_client.close()
        _es_client = None


def _index_name(agent_name: str, suffix: str = "current") -> str:
    return f"{ES_INDEX_PREFIX}_{agent_name}_{suffix}"


MAPPING = {
    "mappings": {
        "properties": {
            "agent_name": {"type": "keyword"},
            "session_id": {"type": "keyword"},
            "session_key": {"type": "keyword"},
            "session_start_datetime": {"type": "date"},
            "message_index": {"type": "integer"},
            "role": {"type": "keyword"},
            "content": {"type": "text", "analyzer": "standard"},
            "timestamp": {"type": "date"},
            "channel": {"type": "keyword"},
            "chat_type": {"type": "keyword"},
        }
    }
}


async def _ensure_index(es, index_name: str):
    """Create index if it doesn't exist."""
    if not await es.indices.exists(index=index_name):
        await es.indices.create(index=index_name, body=MAPPING)


async def search_sessions(agent_name: str, query: str, max_results: int = 50) -> dict:
    """Search session messages across current + old indices."""
    es = await _get_es()
    if not es:
        raise ConnectionError("ES not available")

    indices = []
    current = _index_name(agent_name, "current")
    old = _index_name(agent_name, "old")

    for idx in [current, old]:
        if await es.indices.exists(index=idx):
            indices.append(idx)

    if not indices:
        return {"query": query, "total_matches": 0, "results": []}

    body = {
        "query": {"match": {"content": query}},
        "sort": [{"timestamp": {"order": "desc"}}],
        "size": max_results,
        "highlight": {
            "fields": {"content": {"fragment_size": 150, "number_of_fragments": 1}},
        },
    }

    resp = await es.search(index=",".join(indices), body=body)
    hits = resp["hits"]["hits"]
    total = resp["hits"]["total"]["value"]

    results = []
    for hit in hits:
        src = hit["_source"]
        highlight = hit.get("highlight", {}).get("content", [])
        snippet = highlight[0] if highlight else (src.get("content", "")[:150])
        results.append({
            "session_id": src.get("session_id"),
            "session_key": src.get("session_key"),
            "session_start_datetime": src.get("session_start_datetime"),
            "channel": src.get("channel"),
            "chat_type": src.get("chat_type"),
            "message_index": src.get("message_index"),
            "role": src.get("role"),
            "content_snippet": snippet,
            "timestamp": src.get("timestamp"),
        })

    return {"query": query, "total_matches": total, "results": results}


class SessionIndexer:
    """Background task that periodically syncs session data to ES."""

    def __init__(self, interval: int = ES_SYNC_INTERVAL):
        self._interval = interval
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        if not ES_URL:
            return
        self._running = True
        self._task = asyncio.create_task(self._sync_loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await close_es()

    async def _sync_loop(self):
        while self._running:
            try:
                await self._sync_all()
            except Exception as e:
                print(f"[session_indexer] Sync error: {e}")
            await asyncio.sleep(self._interval)

    async def _sync_all(self):
        """Scan all agents' session directories and index new messages."""
        from ..services import version_db

        es = await _get_es()
        if not es or not await es.ping():
            return

        agents = list_agents()
        db = await version_db.get_db()

        for agent in agents:
            agent_name = agent["name"]
            sessions_dir = Path(SESSION_DATA_DIR) / agent_name.replace("workspace-", "") / "sessions"
            if not sessions_dir.exists():
                continue

            # Read sessions.json for metadata
            sessions_meta = {}
            sessions_json = sessions_dir / "sessions.json"
            if sessions_json.exists():
                try:
                    with open(sessions_json, "r") as f:
                        sessions_meta = json.load(f)
                except (json.JSONDecodeError, OSError):
                    pass

            # Process .jsonl files
            for jsonl_file in sessions_dir.glob("*.jsonl"):
                session_id = jsonl_file.stem
                if session_id.endswith(".lock"):
                    continue

                try:
                    file_size = jsonl_file.stat().st_size
                except OSError:
                    continue

                # Check indexed state
                cursor = await db.execute(
                    "SELECT indexed_lines, file_size, session_start_datetime, indexed_messages FROM session_index_state WHERE agent_name=? AND session_id=?",
                    (agent_name, session_id),
                )
                row = await cursor.fetchone()

                if row:
                    prev_size = row[1]
                    prev_lines = row[0]
                    prev_messages = row[3] if row[3] else 0

                    if file_size == prev_size:
                        continue  # No change

                    if file_size < prev_size:
                        # Session was reset — rotate indices
                        current_idx = _index_name(agent_name, "current")
                        old_idx = _index_name(agent_name, "old")

                        if await es.indices.exists(index=old_idx):
                            await es.indices.delete(index=old_idx)
                        if await es.indices.exists(index=current_idx):
                            # Reindex current to old
                            await es.reindex(
                                body={"source": {"index": current_idx}, "dest": {"index": old_idx}}
                            )
                            await es.indices.delete(index=current_idx)

                        prev_lines = 0
                        prev_messages = 0
                        # Will re-index from scratch below
                else:
                    prev_lines = 0
                    prev_messages = 0

                # Read and index new lines
                try:
                    with open(jsonl_file, "r") as f:
                        all_lines = f.readlines()
                except OSError:
                    continue

                new_lines = all_lines[prev_lines:]
                if not new_lines:
                    continue

                # Find session metadata
                session_key = None
                channel = None
                chat_type = None
                for key, meta in sessions_meta.items():
                    if meta.get("sessionId") == session_id:
                        session_key = key
                        channel = meta.get("lastChannel", "")
                        chat_type = meta.get("chatType", "")
                        break

                # Determine session_start_datetime
                session_start = None
                if prev_lines == 0 and all_lines:
                    try:
                        first = json.loads(all_lines[0])
                        session_start = first.get("timestamp") or datetime.now(timezone.utc).isoformat()
                    except (json.JSONDecodeError, IndexError):
                        session_start = datetime.now(timezone.utc).isoformat()

                # Build bulk actions
                current_idx = _index_name(agent_name, "current")
                await _ensure_index(es, current_idx)

                actions = []
                msg_count = prev_messages
                for i, line in enumerate(new_lines):
                    try:
                        entry = json.loads(line.strip())
                    except json.JSONDecodeError:
                        continue

                    # OpenClaw transcript format: {type: "message", message: {role, content}}
                    if entry.get("type") != "message":
                        continue

                    # Every type=message entry counts as a message for offset alignment with API
                    current_msg_index = msg_count
                    msg_count += 1

                    msg = entry.get("message", {})
                    if not isinstance(msg, dict):
                        continue

                    content = msg.get("content")
                    # Handle Anthropic-style content blocks (list of dicts)
                    if isinstance(content, list):
                        texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                        content = "\n".join(texts) if texts else None
                    elif not isinstance(content, str):
                        content = None

                    if not content:
                        continue

                    role = msg.get("role", "")
                    if role not in ("user", "assistant", "system"):
                        continue

                    doc = {
                        "agent_name": agent_name,
                        "session_id": session_id,
                        "session_key": session_key or "",
                        "session_start_datetime": (session_start or row[2]) if row else session_start,
                        "message_index": current_msg_index,
                        "role": role,
                        "content": content[:10000],  # Limit content size
                        "timestamp": entry.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                        "channel": channel or "",
                        "chat_type": chat_type or "",
                    }

                    actions.append({"index": {"_index": current_idx}})
                    actions.append(doc)

                if actions:
                    await es.bulk(body=actions, refresh="false")

                # Update indexed state
                await db.execute(
                    """INSERT INTO session_index_state (agent_name, session_id, file_path, indexed_lines, indexed_messages, file_size, session_start_datetime, last_indexed_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(agent_name, session_id) DO UPDATE SET
                         indexed_lines=excluded.indexed_lines,
                         indexed_messages=excluded.indexed_messages,
                         file_size=excluded.file_size,
                         session_start_datetime=COALESCE(excluded.session_start_datetime, session_start_datetime),
                         last_indexed_at=excluded.last_indexed_at""",
                    (agent_name, session_id, str(jsonl_file), len(all_lines), msg_count, file_size,
                     session_start, datetime.now(timezone.utc).isoformat()),
                )
                await db.commit()
