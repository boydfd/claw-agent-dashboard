"""System & agent status service — reads process info, session metadata, and gateway logs."""
import os
import re
import time
import json
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import httpx

from ..config import AGENTS_DIR, LOGS_DIR, SESSION_DATA_DIR, OPENCLAW_CONFIG_PATH, GATEWAY_URL, GATEWAY_TOKEN

# Use host /proc if available (mounted from Docker), fallback to local /proc
HOST_PROC = os.environ.get("HOST_PROC", "/host/proc")
if not os.path.exists(HOST_PROC):
    HOST_PROC = "/proc"


# ---------------------------------------------------------------------------
# System metrics
# ---------------------------------------------------------------------------

def get_system_metrics() -> dict:
    """Read system memory and load from /proc."""
    mem = {}
    try:
        with open(f"{HOST_PROC}/meminfo") as f:
            for line in f:
                parts = line.split()
                key = parts[0].rstrip(":")
                if key in ("MemTotal", "MemAvailable", "MemFree", "SwapTotal", "SwapFree"):
                    mem[key] = int(parts[1])  # kB
    except Exception:
        pass

    load = {"1m": 0, "5m": 0, "15m": 0}
    try:
        with open(f"{HOST_PROC}/loadavg") as f:
            parts = f.read().split()
            load = {"1m": float(parts[0]), "5m": float(parts[1]), "15m": float(parts[2])}
    except Exception:
        pass

    total_mb = mem.get("MemTotal", 0) / 1024
    available_mb = mem.get("MemAvailable", mem.get("MemFree", 0)) / 1024
    used_mb = total_mb - available_mb
    usage_pct = (used_mb / total_mb * 100) if total_mb > 0 else 0

    return {
        "memory": {
            "total_mb": round(total_mb),
            "used_mb": round(used_mb),
            "available_mb": round(available_mb),
            "usage_pct": round(usage_pct, 1),
        },
        "swap": {
            "total_mb": round(mem.get("SwapTotal", 0) / 1024),
            "free_mb": round(mem.get("SwapFree", 0) / 1024),
        },
        "load": load,
    }


# ---------------------------------------------------------------------------
# Gateway process status
# ---------------------------------------------------------------------------

def get_gateway_status() -> dict:
    """Detect gateway status via API probe, enriched with /proc details when available."""
    result = {
        "running": False,
        "pid": None,
        "rss_mb": 0,
        "uptime_seconds": 0,
        "threads": 0,
        "state": "unknown",
    }

    # Step 1: API health probe (cross-platform)
    try:
        resp = httpx.get(f"{GATEWAY_URL}/health", timeout=3.0)
        data = resp.json()
        if resp.status_code == 200 and data.get("ok") is True:
            result["running"] = True
            result["state"] = data.get("status", "live")
    except Exception:
        pass

    if not result["running"]:
        return result

    # Step 2: /proc scan for enriched process details (Linux only)
    try:
        for pid_dir in Path(HOST_PROC).iterdir():
            if not pid_dir.name.isdigit():
                continue
            try:
                cmdline = (pid_dir / "cmdline").read_text()
                if "openclaw-gateway" not in cmdline and "openclaw" not in cmdline:
                    continue
                comm = (pid_dir / "comm").read_text().strip()
                if "openclaw" not in comm.lower():
                    continue

                pid = int(pid_dir.name)
                status_text = (pid_dir / "status").read_text()
                status = {}
                for line in status_text.splitlines():
                    parts = line.split(":\t")
                    if len(parts) == 2:
                        status[parts[0].strip()] = parts[1].strip()

                rss_kb = int(status.get("VmRSS", "0 kB").split()[0])
                threads = int(status.get("Threads", "1"))
                state_raw = status.get("State", "? (unknown)")
                state = state_raw.split("(")[-1].rstrip(")") if "(" in state_raw else state_raw

                stat_text = (pid_dir / "stat").read_text()
                stat_after_comm = stat_text[stat_text.rfind(")") + 2:]
                fields = stat_after_comm.split()
                starttime_ticks = int(fields[19])
                clk_tck = os.sysconf("SC_CLK_TCK")
                with open(f"{HOST_PROC}/uptime") as f:
                    system_uptime = float(f.read().split()[0])
                proc_start = starttime_ticks / clk_tck
                proc_uptime = system_uptime - proc_start

                result.update({
                    "pid": pid,
                    "rss_mb": round(rss_kb / 1024),
                    "uptime_seconds": round(proc_uptime),
                    "threads": threads,
                    "state": state,
                })
                break
            except (PermissionError, FileNotFoundError, ValueError, IndexError):
                continue
    except Exception:
        pass

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_uptime(seconds: int) -> str:
    """Format seconds into human-readable uptime."""
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours < 24:
        return f"{hours}h {minutes}m"
    days = hours // 24
    hours = hours % 24
    return f"{days}d {hours}h {minutes}m"


def _format_tokens(count: int) -> str:
    """Format token count as human-readable (e.g., 14k, 1.2M)."""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1000:
        return f"{count / 1000:.0f}k"
    return str(count)


# ---------------------------------------------------------------------------
# Session detail extraction from .jsonl files
# ---------------------------------------------------------------------------

def _extract_session_detail(session_jsonl_path: Path) -> dict:
    """
    Read the tail of a session .jsonl file to extract model, token usage, etc.
    Each line is a JSON object representing an API turn.
    We read the last few lines to get the most recent usage data.
    """
    detail = {
        "model": None,
        "provider": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "total_tokens": 0,
        "max_tokens": 0,
        "cache_rate": 0,
        "turns": 0,
    }

    if not session_jsonl_path.exists():
        return detail

    try:
        # Read last portion of file (up to 200KB) for efficiency
        file_size = session_jsonl_path.stat().st_size
        read_size = min(file_size, 200 * 1024)

        with open(session_jsonl_path, "rb") as f:
            if file_size > read_size:
                f.seek(file_size - read_size)
                # Skip partial first line
                f.readline()
            lines = f.readlines()

        total_input = 0
        total_output = 0
        total_cache_creation = 0
        total_cache_read = 0
        model = None
        provider = None
        turns = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            # OpenClaw session format: {type, id, parentId, timestamp, message}
            # Model and usage live inside entry["message"] for assistant messages
            msg = entry.get("message") or entry

            # Look for model info
            if "model" in msg:
                model = msg["model"]
            elif "model" in entry:
                model = entry["model"]

            # Look for provider info
            if "provider" in msg:
                provider = msg["provider"]
            elif "provider" in entry:
                provider = entry["provider"]

            # Look for usage data — OpenClaw uses {input, output, cacheRead, cacheWrite, totalTokens}
            usage = msg.get("usage") or entry.get("usage")
            if usage:
                if "input" in usage:
                    # OpenClaw format: input/output/cacheRead/cacheWrite
                    total_input += usage.get("input", 0)
                    total_output += usage.get("output", 0)
                    total_cache_creation += usage.get("cacheWrite", 0)
                    total_cache_read += usage.get("cacheRead", 0)
                    turns += 1
                elif "input_tokens" in usage:
                    # Standard Anthropic format fallback
                    total_input += usage.get("input_tokens", 0)
                    total_output += usage.get("output_tokens", 0)
                    total_cache_creation += usage.get("cache_creation_input_tokens", 0)
                    total_cache_read += usage.get("cache_read_input_tokens", 0)
                    turns += 1

        total = total_input + total_output
        cache_total = total_cache_creation + total_cache_read
        # Cache rate: percentage of tokens served from cache
        # = cacheRead / (input + cacheRead) * 100
        total_with_cache = total_input + total_cache_read
        cache_rate = (total_cache_read / total_with_cache * 100) if total_with_cache > 0 else 0

        detail.update({
            "model": model,
            "provider": provider,
            "input_tokens": total_input,
            "output_tokens": total_output,
            "cache_creation_tokens": total_cache_creation,
            "cache_read_tokens": total_cache_read,
            "total_tokens": total,
            "cache_rate": round(cache_rate, 1),
            "turns": turns,
        })
    except Exception:
        pass

    return detail


def _find_session_jsonl(agent_name: str, session_id: str) -> Optional[Path]:
    """Find a session .jsonl file by session ID."""
    # Try the session data dir first (host mount), then AGENTS_DIR
    for base in [Path(SESSION_DATA_DIR), Path(AGENTS_DIR) / agent_name / "sessions"]:
        if not base.exists():
            continue
        # Session files might be named with the session ID
        for pattern in [f"*{session_id}*.jsonl", "*.jsonl"]:
            for f in base.glob(pattern):
                if session_id in f.name and not f.name.endswith(".deleted.jsonl"):
                    return f
    return None


# ---------------------------------------------------------------------------
# Session message history (paginated)
# ---------------------------------------------------------------------------

def _parse_message_content(content) -> list:
    """Parse message content blocks into a renderable format."""
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        result = []
        for block in content:
            if isinstance(block, str):
                result.append({"type": "text", "text": block})
            elif isinstance(block, dict):
                btype = block.get("type", "text")
                if btype == "thinking":
                    result.append({
                        "type": "thinking",
                        "text": block.get("thinking", ""),
                    })
                elif btype == "toolCall":
                    raw_args = block.get("arguments", "")
                    # Ensure arguments is a string (may be dict in OpenClaw format)
                    if isinstance(raw_args, dict):
                        raw_args = json.dumps(raw_args, indent=2, ensure_ascii=False)
                    elif not isinstance(raw_args, str):
                        raw_args = str(raw_args)
                    result.append({
                        "type": "toolCall",
                        "name": block.get("name", "unknown"),
                        "arguments": raw_args,
                    })
                elif btype == "toolResult":
                    raw_text = block.get("text", block.get("content", ""))
                    # Ensure text is a string
                    if isinstance(raw_text, (list, dict)):
                        raw_text = json.dumps(raw_text, indent=2, ensure_ascii=False)
                    elif not isinstance(raw_text, str):
                        raw_text = str(raw_text)
                    result.append({
                        "type": "toolResult",
                        "text": raw_text,
                        "isError": block.get("isError", False),
                    })
                else:
                    # text or other types
                    result.append({
                        "type": "text",
                        "text": block.get("text", str(block)),
                    })
        return result
    return [{"type": "text", "text": str(content)}]


def get_session_messages(agent_name: str, session_id: str, offset: int = 0, limit: int = 50) -> dict:
    """
    Read a session .jsonl file and return paginated messages.
    Each line in the file is a JSON object representing a message/event.
    Returns { messages: [...], total: N, has_more: bool }
    """
    jsonl_path = _find_session_jsonl(agent_name, session_id)
    if not jsonl_path or not jsonl_path.exists():
        return {"messages": [], "total": 0, "has_more": False}

    try:
        # Read all lines and filter to actual messages
        all_messages = []
        with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

                # Only include message-type entries (skip internal/meta entries)
                entry_type = entry.get("type", "")
                if entry_type not in ("message", ""):
                    # Allow entries without 'type' if they have 'message' field
                    if "message" not in entry and "role" not in entry:
                        continue

                # Extract the message part
                msg = entry.get("message") or entry
                role = msg.get("role", "unknown")
                content_raw = msg.get("content", "")
                timestamp = entry.get("timestamp", "")
                model = msg.get("model")
                provider = msg.get("provider") or entry.get("provider")
                usage = msg.get("usage")

                parsed_content = _parse_message_content(content_raw)

                all_messages.append({
                    "timestamp": timestamp,
                    "role": role,
                    "content": parsed_content,
                    "model": model,
                    "provider": provider,
                    "usage": usage,
                })

        total = len(all_messages)
        sliced = all_messages[offset:offset + limit]
        has_more = (offset + limit) < total

        return {
            "messages": sliced,
            "total": total,
            "has_more": has_more,
        }

    except Exception as e:
        return {"messages": [], "total": 0, "has_more": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Agent status
# ---------------------------------------------------------------------------

def get_agent_status(agent_name: str) -> dict:
    """Get status for a specific agent by reading its sessions.json,
    .jsonl.lock files (working indicator), and .jsonl mtime (activity indicator)."""
    agent_dir = Path(AGENTS_DIR) / agent_name
    session_dir = agent_dir / "sessions"
    sessions_file = session_dir / "sessions.json"

    sessions = []
    now = time.time()
    now_ms = int(now * 1000)

    # Track signals for overall status
    any_has_lock = False
    min_jsonl_age = None  # seconds since most recent .jsonl mtime

    if sessions_file.exists():
        try:
            data = json.loads(sessions_file.read_text())
            for key, sess in data.items():
                updated_at = sess.get("updatedAt", 0)
                age_seconds = (now_ms - updated_at) / 1000 if updated_at else None

                session_id = sess.get("sessionId", "")

                # Signal 1: Check .jsonl.lock file existence
                has_lock = False
                if session_id and session_dir.exists():
                    for lock_file in session_dir.glob(f"*{session_id}*.jsonl.lock"):
                        has_lock = True
                        break

                # Signal 2: Check .jsonl file mtime
                jsonl_age_seconds = None
                if session_id and session_dir.exists():
                    for jf in session_dir.glob(f"*{session_id}*.jsonl"):
                        if jf.name.endswith(".deleted.jsonl") or jf.name.endswith(".lock"):
                            continue
                        try:
                            mtime = jf.stat().st_mtime
                            jsonl_age_seconds = round(now - mtime)
                        except OSError:
                            pass
                        break

                if has_lock:
                    any_has_lock = True
                if jsonl_age_seconds is not None:
                    if min_jsonl_age is None or jsonl_age_seconds < min_jsonl_age:
                        min_jsonl_age = jsonl_age_seconds

                sessions.append({
                    "session_key": key,
                    "session_id": session_id,
                    "channel": sess.get("lastChannel", "unknown"),
                    "chat_type": sess.get("chatType", "unknown"),
                    "updated_at": updated_at,
                    "age_seconds": round(age_seconds) if age_seconds else None,
                    "age_human": _format_uptime(round(age_seconds)) if age_seconds else "unknown",
                    "aborted": sess.get("abortedLastRun", False),
                    "has_lock": has_lock,
                    "jsonl_age_seconds": jsonl_age_seconds,
                })
        except Exception:
            pass

    sessions.sort(key=lambda s: s.get("updated_at", 0), reverse=True)

    # Determine overall agent status using 3-tier priority
    if not sessions:
        status = "unknown"
        status_label = "No sessions"
    else:
        most_recent = sessions[0]
        age = most_recent.get("age_seconds")

        # Priority 0: Aborted takes precedence
        if most_recent.get("aborted"):
            status = "error"
            status_label = "Last run aborted"
        # Priority 1: Any .lock file → working
        elif any_has_lock:
            status = "working"
            status_label = "Working"
        # Priority 2: .jsonl mtime < 30s → active
        elif min_jsonl_age is not None and min_jsonl_age < 30:
            status = "active"
            status_label = "Active"
        # Priority 3: Fall back to sessions.json updatedAt
        elif age is not None and age < 120:
            status = "active"
            status_label = "Active"
        elif age is not None and age < 600:
            status = "idle"
            status_label = "Idle"
        elif age is not None and age < 1800:
            status = "idle"
            status_label = f"Idle ({most_recent['age_human']})"
        else:
            status = "dormant"
            status_label = f"Dormant ({most_recent['age_human']})"

    active_files = list(session_dir.glob("*.jsonl")) if session_dir.exists() else []
    deleted_files = list(session_dir.glob("*.deleted.*")) if session_dir.exists() else []

    return {
        "agent_name": agent_name,
        "status": status,
        "status_label": status_label,
        "sessions": sessions,
        "session_files": {
            "active": len(active_files),
            "deleted": len(deleted_files),
        },
    }


def get_agent_detail(agent_name: str) -> dict:
    """
    Get comprehensive status for a specific agent:
    - Basic agent status & sessions
    - Enhanced session details (model, tokens, cache rate) from .jsonl files
    - Recent events filtered for this agent from gateway logs
    - Compact gateway/system summary
    """
    # Basic agent status
    agent_status = get_agent_status(agent_name)

    # Enhance each session with detail from .jsonl files
    agent_dir = Path(AGENTS_DIR) / agent_name
    session_dir = agent_dir / "sessions"

    for sess in agent_status["sessions"]:
        sid = sess.get("session_id", "")
        if not sid:
            continue

        # Try to find the .jsonl file for this session
        jsonl_path = None
        if session_dir.exists():
            for f in session_dir.glob("*.jsonl"):
                if sid in f.name and not f.name.endswith(".deleted.jsonl"):
                    jsonl_path = f
                    break

        if jsonl_path:
            detail = _extract_session_detail(jsonl_path)
            sess["model"] = detail["model"]
            sess["provider"] = detail["provider"]
            sess["input_tokens"] = detail["input_tokens"]
            sess["output_tokens"] = detail["output_tokens"]
            sess["total_tokens"] = detail["total_tokens"]
            sess["cache_rate"] = detail["cache_rate"]
            sess["cache_creation_tokens"] = detail["cache_creation_tokens"]
            sess["cache_read_tokens"] = detail["cache_read_tokens"]
            sess["turns"] = detail["turns"]
            # Human-readable token summary
            if detail["total_tokens"] > 0:
                sess["token_summary"] = (
                    f"{_format_tokens(detail['input_tokens'])}/{_format_tokens(detail['output_tokens'])}"
                )
            else:
                sess["token_summary"] = None
        else:
            sess["model"] = None
            sess["provider"] = None
            sess["input_tokens"] = 0
            sess["output_tokens"] = 0
            sess["total_tokens"] = 0
            sess["cache_rate"] = 0
            sess["cache_creation_tokens"] = 0
            sess["cache_read_tokens"] = 0
            sess["turns"] = 0
            sess["token_summary"] = None

    # Get agent-specific events from gateway logs
    # Extract the short agent name for log filtering
    short_name = agent_name
    if "/" in agent_name:
        short_name = agent_name.split("/")[-1]
    events = get_recent_events(agent_filter=short_name, limit=50)

    # Compact gateway status
    gw = get_gateway_status()
    gw["uptime_human"] = _format_uptime(gw["uptime_seconds"]) if gw["running"] else "down"

    # Compact system summary
    sys_metrics = get_system_metrics()

    return {
        "timestamp": int(time.time() * 1000),
        "agent": agent_status,
        "events": events,
        "gateway": {
            "running": gw["running"],
            "uptime_human": gw["uptime_human"],
            "rss_mb": gw["rss_mb"],
        },
        "system": {
            "memory_pct": sys_metrics["memory"]["usage_pct"],
            "memory_used_mb": sys_metrics["memory"]["used_mb"],
            "memory_total_mb": sys_metrics["memory"]["total_mb"],
            "load_1m": sys_metrics["load"]["1m"],
        },
    }


# ---------------------------------------------------------------------------
# All agents
# ---------------------------------------------------------------------------

def get_all_agents_status() -> list:
    """Get status summary for all agents.
    
    Cross-references agents/*/sessions with workspace-* directories
    to avoid showing orphaned session-only agents (e.g. stale data).
    """
    agents_dir = Path(AGENTS_DIR) / "agents"
    base_dir = Path(AGENTS_DIR)
    result = []
    if agents_dir.exists():
        # Build set of valid agent ids from workspace directories
        valid_agents = set()
        for entry in base_dir.iterdir():
            if entry.is_dir():
                if entry.name == "workspace":
                    valid_agents.add("main")
                elif entry.name.startswith("workspace-"):
                    valid_agents.add(entry.name.replace("workspace-", "", 1))

        for agent_dir in sorted(agents_dir.iterdir()):
            if agent_dir.is_dir() and agent_dir.name in valid_agents:
                status = get_agent_status(f"agents/{agent_dir.name}")
                status["agent_name"] = agent_dir.name
                result.append(status)
    return result


# ---------------------------------------------------------------------------
# Gateway log event parsing
# ---------------------------------------------------------------------------

def _get_log_files() -> list[Path]:
    """Get gateway log files sorted by date (most recent first)."""
    logs_dir = Path(LOGS_DIR)
    if not logs_dir.exists():
        return []

    log_files = []
    for f in logs_dir.glob("openclaw-*.log"):
        log_files.append(f)

    # Sort by filename (contains date) descending
    log_files.sort(key=lambda f: f.name, reverse=True)
    return log_files


def _classify_event(entry: dict) -> Optional[dict]:
    """
    Classify a gateway log entry into a meaningful event.
    Log format: JSON with _meta.logLevelName, _meta.date, 0 (subsystem JSON string), 1 (message)
    """
    try:
        meta = entry.get("_meta", {})
        level = meta.get("logLevelName", "").upper()
        date_str = meta.get("date", "")

        # Parse subsystem — field "0" is often a JSON string like '{"subsystem":"gateway/ws"}'
        raw_sub = entry.get("0", "")
        subsystem = str(raw_sub)
        if isinstance(raw_sub, str):
            try:
                sub_obj = json.loads(raw_sub)
                if isinstance(sub_obj, dict) and "subsystem" in sub_obj:
                    subsystem = sub_obj["subsystem"]
            except (json.JSONDecodeError, ValueError):
                pass

        message = str(entry.get("1", ""))
        # Some logs use numeric keys for additional data
        extra = str(entry.get("2", ""))

        event = {
            "time": date_str,
            "level": level,
            "subsystem": subsystem,
            "message": message,
            "type": "info",
            "icon": "ℹ️",
            "agent": None,
        }

        msg_lower = message.lower()
        sub_lower = subsystem.lower()

        # Skip noisy websocket connection/disconnection events
        if "gateway/ws" in sub_lower:
            ws_noise = ["connected", "disconnected", "handshake timeout", "handshake-timeout", "⇄ res", "⇄ req"]
            if any(kw in msg_lower or kw in message for kw in ws_noise):
                return None

        # Skip plugin warnings (repetitive)
        if "plugins" in sub_lower and "plugins.allow is empty" in message:
            return None

        # Gateway restart
        if "start" in msg_lower and ("gateway" in sub_lower or "server" in sub_lower):
            event["type"] = "gateway_start"
            event["icon"] = "🔄"
            event["summary"] = "Gateway started"
            return event

        # OOM events
        if "oom" in msg_lower or "out of memory" in msg_lower or "killed" in msg_lower:
            event["type"] = "oom"
            event["icon"] = "💀"
            event["summary"] = f"OOM: {message[:80]}"
            return event

        # Error events
        if level in ("ERROR", "FATAL"):
            event["type"] = "error"
            event["icon"] = "❌"
            event["summary"] = f"{subsystem}: {message[:80]}"
            return event

        # Warning events
        if level == "WARN":
            event["type"] = "warning"
            event["icon"] = "⚠️"
            event["summary"] = f"{subsystem}: {message[:80]}"
            return event

        # Agent-related messages
        # Look for agent names in message or subsystem
        agent_match = re.search(r'\b(developer|daily|researcher|mock|assistant)\b', msg_lower + " " + sub_lower)
        if agent_match:
            event["agent"] = agent_match.group(1)

        # Message sending/receiving
        if any(kw in msg_lower for kw in ["sending message", "send message", "replied", "response"]):
            event["type"] = "message_sent"
            event["icon"] = "💬"
            event["summary"] = f"{subsystem}: {message[:80]}"
            return event

        if any(kw in msg_lower for kw in ["received message", "incoming", "new message"]):
            event["type"] = "message_received"
            event["icon"] = "📩"
            event["summary"] = f"{subsystem}: {message[:80]}"
            return event

        # Session events
        if any(kw in msg_lower for kw in ["session created", "new session", "creating session"]):
            event["type"] = "session_created"
            event["icon"] = "🆕"
            event["summary"] = f"Session created: {message[:60]}"
            return event

        if any(kw in msg_lower for kw in ["session reset", "resetting session", "session cleared"]):
            event["type"] = "session_reset"
            event["icon"] = "♻️"
            event["summary"] = f"Session reset: {message[:60]}"
            return event

        # Heartbeat
        if "heartbeat" in msg_lower:
            event["type"] = "heartbeat"
            event["icon"] = "💓"
            event["summary"] = f"{subsystem}: heartbeat"
            return event

        # API/model events
        if any(kw in msg_lower for kw in ["api call", "model", "claude", "anthropic"]):
            event["type"] = "api_call"
            event["icon"] = "🤖"
            event["summary"] = f"{subsystem}: {message[:80]}"
            return event

        # If it's a notable level or subsystem, include it
        if level in ("ERROR", "WARN", "FATAL", "INFO"):
            event["type"] = "log"
            event["icon"] = "📝"
            event["summary"] = f"{subsystem}: {message[:80]}"
            return event

        return None  # Skip debug/trace level noise

    except Exception:
        return None


def get_recent_events(agent_filter: Optional[str] = None, limit: int = 100) -> list:
    """
    Parse gateway logs and return recent meaningful events.
    Optionally filter by agent name.
    """
    events = []
    log_files = _get_log_files()

    if not log_files:
        return events

    # Read at most 2 log files (today + yesterday)
    for log_file in log_files[:2]:
        try:
            # Read last portion of file for efficiency
            file_size = log_file.stat().st_size
            read_size = min(file_size, 500 * 1024)  # Last 500KB

            with open(log_file, "rb") as f:
                if file_size > read_size:
                    f.seek(file_size - read_size)
                    f.readline()  # Skip partial line
                lines = f.readlines()

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

                event = _classify_event(entry)
                if event is None:
                    continue

                # Apply agent filter
                if agent_filter:
                    msg_lower = (event.get("message", "") + " " + event.get("subsystem", "")).lower()
                    if agent_filter.lower() not in msg_lower and event.get("agent") != agent_filter.lower():
                        # Still include global events (gateway start, OOM, errors)
                        if event["type"] not in ("gateway_start", "oom", "error"):
                            continue

                events.append(event)

        except Exception:
            continue

    # Sort by time descending, take limit
    events.sort(key=lambda e: e.get("time", ""), reverse=True)
    return events[:limit]


# ---------------------------------------------------------------------------
# Full status (legacy — used by global dashboard)
# ---------------------------------------------------------------------------

def get_full_status() -> dict:
    """Get complete system status."""
    gw = get_gateway_status()
    gw["uptime_human"] = _format_uptime(gw["uptime_seconds"]) if gw["running"] else "down"

    return {
        "timestamp": int(time.time() * 1000),
        "gateway": gw,
        "system": get_system_metrics(),
        "agents": get_all_agents_status(),
    }


# ---------------------------------------------------------------------------
# OpenClaw model configuration
# ---------------------------------------------------------------------------

def _strip_json_comments(text: str) -> str:
    """Strip // comments and trailing commas from JSON-with-comments text."""
    lines = []
    for line in text.split("\n"):
        # Remove // comments (but not inside strings — simple heuristic)
        stripped = line.lstrip()
        if stripped.startswith("//"):
            continue
        # Remove inline // comments (outside of quoted strings)
        in_string = False
        result = []
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '"' and (i == 0 or line[i - 1] != '\\'):
                in_string = not in_string
            elif ch == '/' and not in_string and i + 1 < len(line) and line[i + 1] == '/':
                break
            result.append(ch)
            i += 1
        lines.append("".join(result))

    joined = "\n".join(lines)

    # Remove trailing commas before } or ]
    joined = re.sub(r',\s*([}\]])', r'\1', joined)

    return joined


def get_available_models() -> dict:
    """Read OpenClaw config file and extract available models."""
    config_path = Path(OPENCLAW_CONFIG_PATH)
    if not config_path.exists():
        return {"models": [], "default": None}

    try:
        raw = config_path.read_text(encoding="utf-8")
        cleaned = _strip_json_comments(raw)
        config = json.loads(cleaned)
    except Exception as e:
        return {"models": [], "default": None, "error": str(e)}

    # models section: top-level "models" has providers dict
    models_section = config.get("models", {})
    # agent model config: agents.defaults.model has primary/fallbacks
    agent_model = config.get("agents", {}).get("defaults", {}).get("model", {})

    primary = agent_model.get("primary", "")
    fallbacks = agent_model.get("fallbacks", [])

    # Collect all models from providers (providers is a dict, not a list)
    models = []
    seen_ids = set()

    providers = models_section.get("providers", {})
    if isinstance(providers, dict):
        for provider_name, provider_cfg in providers.items():
            provider_models = provider_cfg.get("models", []) if isinstance(provider_cfg, dict) else []
            for m in provider_models:
                if not isinstance(m, dict):
                    continue
                mid = m.get("id", "")
                name = m.get("name", mid)
                # Full model ID includes provider prefix
                full_id = f"{provider_name}/{mid}" if mid else ""
                if full_id and full_id not in seen_ids:
                    seen_ids.add(full_id)
                    models.append({
                        "id": full_id,
                        "name": name,
                        "primary": full_id == primary,
                    })

    # Ensure primary and fallbacks are listed even if not in providers
    for model_id in [primary] + fallbacks:
        if model_id and model_id not in seen_ids:
            seen_ids.add(model_id)
            short_name = model_id.split("/")[-1] if "/" in model_id else model_id
            models.append({
                "id": model_id,
                "name": short_name,
                "primary": model_id == primary,
            })

    return {
        "models": models,
        "default": primary or None,
    }


async def create_new_session(agent: str, session_key: str | None = None) -> dict:
    """Reset a session to match OpenClaw's native /new behavior exactly.

    Native /new does:
    1. Generate a new sessionId + sessionFile within the SAME session key
    2. Update sessions.json (clear systemSent, model overrides, etc.)
    3. Write session header to new .jsonl transcript
    4. Send bare session reset prompt so agent executes startup sequence

    When session_key is provided, we reset that specific channel session.
    When omitted, we find the first nextcloud-talk:group session for the agent.
    """
    import uuid
    from datetime import datetime, timezone

    agent_dir = Path(AGENTS_DIR) / "agents" / agent
    sessions_file = agent_dir / "sessions" / "sessions.json"

    if not sessions_file.exists():
        raise FileNotFoundError(f"sessions.json not found for agent {agent}")

    with open(sessions_file) as f:
        sessions_data = json.load(f)

    # Find the target session entry
    target_key = None
    target_entry = None

    if session_key:
        # Try exact match first, then fuzzy match
        input_key = session_key.strip()
        normalized = input_key
        if input_key.startswith(f"agent:{agent}:"):
            normalized = input_key[len(f"agent:{agent}:"):]

        for key, val in sessions_data.items():
            origin_to = (val.get("origin", {}) or {}).get("to") or ""
            if (
                key == input_key
                or key == f"agent:{agent}:{normalized}"
                or key.endswith(":" + normalized)
                or origin_to == input_key
            ):
                target_key = key
                target_entry = val
                break
    else:
        # Default: find first nextcloud-talk:group session
        for key, val in sessions_data.items():
            if "nextcloud-talk:group:" in key:
                target_key = key
                target_entry = val
                break

    if target_entry is None:
        raise ValueError(f"No session found for agent {agent} (key={session_key})")

    # Step 1: Generate new sessionId and sessionFile
    new_session_id = str(uuid.uuid4())
    sessions_dir = agent_dir / "sessions"
    # Compute the host-side session file path from AGENTS_HOST_DIR.
    # AGENTS_HOST_DIR mirrors the host path that maps to AGENTS_DIR inside
    # the container (e.g. "~/.openclaw" on the host → "/agents" in container).
    agents_host = os.environ.get("AGENTS_HOST_DIR", "")
    if agents_host:
        new_session_file_host = str(
            Path(agents_host) / "agents" / agent / "sessions" / f"{new_session_id}.jsonl"
        )
    else:
        # Fallback: construct from AGENTS_DIR (works when running outside container)
        new_session_file_host = str(
            Path(AGENTS_DIR) / "agents" / agent / "sessions" / f"{new_session_id}.jsonl"
        )
    new_session_file_local = sessions_dir / f"{new_session_id}.jsonl"

    # Step 2: Update sessions.json — preserve thinkingLevel, verboseLevel,
    # modelOverride, providerOverride, label (same as native /new)
    old_entry = dict(target_entry)
    target_entry["sessionId"] = new_session_id
    target_entry["sessionFile"] = new_session_file_host
    target_entry["updatedAt"] = int(time.time() * 1000)
    target_entry["systemSent"] = False
    target_entry["abortedLastRun"] = False
    # Clear runtime model state (will be re-resolved on next run)
    for clear_key in ["model", "modelProvider", "contextTokens",
                      "systemPromptReport", "fallbackNoticeSelectedModel",
                      "fallbackNoticeActiveModel", "fallbackNoticeReason"]:
        target_entry.pop(clear_key, None)

    sessions_data[target_key] = target_entry
    with open(sessions_file, "w") as f:
        json.dump(sessions_data, f, indent=2)

    # Step 3: Write session header to new .jsonl transcript
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    session_event = {
        "type": "session",
        "sessionId": new_session_id,
        "timestamp": now_iso,
    }
    with open(new_session_file_local, "w") as f:
        f.write(json.dumps(session_event) + "\n")

    # Step 4: Send bare session reset prompt to agent via Gateway API
    # This is the actual prompt that triggers agent startup
    now_ms = int(time.time() * 1000)
    now_dt = datetime.now(timezone.utc)
    time_str = now_dt.strftime("%A, %B %-d") + now_dt.strftime(", %Y — %-I:%M %p (UTC) / %Y-%m-%d %H:%M UTC")
    # Match OpenClaw's exact format for appendCronStyleCurrentTimeLine
    day_suffix = {1: "st", 2: "nd", 3: "rd", 21: "st", 22: "nd", 23: "rd", 31: "st"}.get(now_dt.day, "th")
    day_with_suffix = f"{now_dt.day}{day_suffix}"
    time_line = now_dt.strftime(f"%A, %B {day_with_suffix}, %Y — %-I:%M %p (UTC) / %Y-%m-%d %H:%M UTC")
    reset_prompt = (
        "A new session was started via /new or /reset. "
        "Execute your Session Startup sequence now - read the required files "
        "before responding to the user. Then greet the user in your configured "
        "persona, if one is provided. Be yourself - use your defined voice, "
        "mannerisms, and mood. Keep it to 1-3 sentences and ask what they want "
        "to do. If the runtime model differs from default_model in the system "
        "prompt, mention the default model. Do not mention internal steps, "
        "files, tools, or reasoning.\n"
        f"Current time: {time_line}"
    )

    # Send as a regular message via Gateway (not /new — that won't trigger reset)
    url = f"{GATEWAY_URL}/v1/responses"
    body = {
        "model": f"openclaw:{agent}",
        "input": reset_prompt,
    }
    headers = {"Content-Type": "application/json"}
    if GATEWAY_TOKEN:
        headers["Authorization"] = f"Bearer {GATEWAY_TOKEN}"
    # Bind to the session key so Gateway routes to the right session
    headers["x-openclaw-session-key"] = target_key

    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        result = resp.json()

    return {
        "success": True,
        "previous_session_id": old_entry.get("sessionId"),
        "new_session_id": new_session_id,
        "session_key": target_key,
        "agent_response": result,
    }


async def switch_session_model(agent: str, model: str, session_key: str) -> dict:
    """Switch model for an existing session by appending a model_change event.

    Accepts either full session key (agent:xxx:...) or channel key
    (nextcloud-talk:group:xxx / nextcloud-talk:xxx) for robust matching.
    """
    import uuid
    from datetime import datetime, timezone

    agent_dir = Path(AGENTS_DIR) / "agents" / agent
    sessions_file = agent_dir / "sessions" / "sessions.json"

    if not sessions_file.exists():
        raise FileNotFoundError(f"sessions.json not found for agent {agent}")

    with open(sessions_file) as f:
        sessions_data = json.load(f)

    # Normalize input session key variants
    input_key = (session_key or "").strip()
    normalized_channel_key = input_key
    if input_key.startswith(f"agent:{agent}:"):
        normalized_channel_key = input_key[len(f"agent:{agent}:") :]
    if normalized_channel_key.startswith("nextcloud-talk:group:"):
        normalized_origin_to = normalized_channel_key.replace("nextcloud-talk:group:", "nextcloud-talk:", 1)
    else:
        normalized_origin_to = normalized_channel_key

    entry = None
    matched_key = None
    for key, val in sessions_data.items():
        origin_to = (val.get("origin", {}) or {}).get("to") or ""

        if (
            key == input_key
            or key == f"agent:{agent}:{normalized_channel_key}"
            or key.endswith(":" + normalized_channel_key)
            or origin_to == input_key
            or origin_to == normalized_origin_to
        ):
            entry = val
            matched_key = key
            break

    if entry is None:
        raise ValueError(f"Session not found for key: {session_key}")

    session_file = entry.get("sessionFile")
    if not session_file:
        raise ValueError(f"No sessionFile in session entry for key: {session_key}")

    # Map host absolute path into mounted /agents path if needed
    sf_path = Path(session_file)
    session_file_local = sf_path
    if not sf_path.exists():
        parts = sf_path.parts
        try:
            agents_idx = next(i for i, p in enumerate(parts) if p == "agents" and i + 1 < len(parts))
            relative = Path(*parts[agents_idx:])
            session_file_local = Path(AGENTS_DIR) / relative
        except StopIteration:
            session_file_local = sf_path

    if "/" in model:
        provider, model_id = model.split("/", 1)
    else:
        provider = ""
        model_id = model

    event = {
        "type": "model_change",
        "id": uuid.uuid4().hex[:8],
        "parentId": None,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "provider": provider,
        "modelId": model_id,
    }

    with open(session_file_local, "a") as f:
        f.write(json.dumps(event) + "\n")

    return {
        "success": True,
        "model": model,
        "session_key": session_key,
        "matched_session_key": matched_key,
    }
