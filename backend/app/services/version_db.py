"""Version database — SQLite connection management and CRUD operations."""
import asyncio
import hashlib
from pathlib import Path

import aiosqlite

from ..config import DATA_DIR

DB_PATH = Path(DATA_DIR) / "versions.db"

_db: aiosqlite.Connection | None = None
_lock = asyncio.Lock()


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        async with _lock:
            if _db is None:
                DB_PATH.parent.mkdir(parents=True, exist_ok=True)
                _db = await aiosqlite.connect(str(DB_PATH))
                _db.row_factory = aiosqlite.Row
                await _db.execute("PRAGMA journal_mode=WAL")
                await _db.execute("PRAGMA foreign_keys=ON")
    return _db


async def init_db():
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS agents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_name  TEXT NOT NULL UNIQUE,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS file_versions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id        INTEGER NOT NULL REFERENCES agents(id),
            file_path       TEXT NOT NULL,
            version_num     INTEGER NOT NULL,
            content         TEXT NOT NULL,
            content_hash    TEXT NOT NULL,
            source          TEXT NOT NULL,
            likely_openclaw BOOLEAN DEFAULT FALSE,
            commit_msg      TEXT,
            ai_summary      TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(agent_id, file_path, version_num)
        );

        CREATE INDEX IF NOT EXISTS idx_versions_file
            ON file_versions(agent_id, file_path, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_versions_hash
            ON file_versions(agent_id, file_path, content_hash);

        CREATE TABLE IF NOT EXISTS tracked_files (
            agent_id      INTEGER NOT NULL REFERENCES agents(id),
            file_path     TEXT NOT NULL,
            current_hash  TEXT NOT NULL,
            last_scanned  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(agent_id, file_path)
        );

        CREATE TABLE IF NOT EXISTS variables (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            value       TEXT NOT NULL,
            type        TEXT NOT NULL DEFAULT 'text' CHECK(type IN ('text', 'secret')),
            scope       TEXT NOT NULL DEFAULT 'global' CHECK(scope IN ('global', 'agent', 'blueprint')),
            agent_id    INTEGER REFERENCES agents(id),
            description TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CHECK((scope = 'global' AND agent_id IS NULL) OR (scope IN ('agent', 'blueprint') AND agent_id IS NOT NULL))
        );

        CREATE TABLE IF NOT EXISTS templates (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id         INTEGER NOT NULL REFERENCES agents(id),
            file_path        TEXT NOT NULL,
            content          TEXT NOT NULL,
            base_template_id INTEGER,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(agent_id, file_path)
        );

        CREATE TABLE IF NOT EXISTS agent_blueprints (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            description TEXT,
            agent_id    INTEGER NOT NULL REFERENCES agents(id),
            parent_id   INTEGER REFERENCES agent_blueprints(id),
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS agent_derivations (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            blueprint_id  INTEGER NOT NULL REFERENCES agent_blueprints(id),
            agent_id      INTEGER NOT NULL UNIQUE REFERENCES agents(id),
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS derivation_overrides (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            derivation_id  INTEGER NOT NULL REFERENCES agent_derivations(id),
            file_path      TEXT NOT NULL,
            overridden_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(derivation_id, file_path)
        );
    """)
    await db.commit()

    await db.execute("""
        CREATE TABLE IF NOT EXISTS blueprint_pending_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blueprint_id INTEGER NOT NULL REFERENCES agent_blueprints(id),
            file_path TEXT NOT NULL,
            change_type TEXT NOT NULL CHECK(change_type IN ('modified', 'added', 'deleted')),
            old_content TEXT,
            new_content TEXT,
            old_hash TEXT,
            new_hash TEXT,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'accepted', 'rejected')),
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP
        )
    """)
    await db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_changes_unique
        ON blueprint_pending_changes(blueprint_id, file_path)
        WHERE status = 'pending'
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS agent_pending_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER NOT NULL REFERENCES agents(id),
            file_path TEXT NOT NULL,
            change_type TEXT NOT NULL CHECK(change_type IN ('modified', 'added')),
            old_content TEXT,
            new_content TEXT,
            old_hash TEXT,
            new_hash TEXT,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'accepted', 'rejected')),
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP
        )
    """)
    await db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_pending_changes_unique
            ON agent_pending_changes(agent_id, file_path)
            WHERE status = 'pending'
    """)
    await db.commit()

    await db.execute("""
        CREATE TABLE IF NOT EXISTS session_index_state (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name            TEXT NOT NULL,
            session_id            TEXT NOT NULL,
            file_path             TEXT NOT NULL,
            indexed_lines         INTEGER NOT NULL DEFAULT 0,
            indexed_messages      INTEGER NOT NULL DEFAULT 0,
            file_size             INTEGER NOT NULL DEFAULT 0,
            session_start_datetime TEXT,
            last_indexed_at       TEXT,
            UNIQUE(agent_name, session_id)
        )
    """)
    await db.commit()

    # Partial unique indexes for variables (added after executescript)
    await db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_variables_global_unique
            ON variables(name) WHERE scope = 'global'
    """)
    await db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_variables_agent_unique
            ON variables(name, agent_id) WHERE scope = 'agent'
    """)
    await db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_variables_blueprint_unique
            ON variables(name, agent_id) WHERE scope = 'blueprint'
    """)
    await db.commit()

    # Migration: add is_virtual to agents table
    try:
        await db.execute(
            "ALTER TABLE agents ADD COLUMN is_virtual BOOLEAN NOT NULL DEFAULT FALSE"
        )
        await db.commit()
    except Exception:
        pass  # Column already exists

    # Migration: recreate variables table with blueprint scope support
    # Uses explicit BEGIN/COMMIT to ensure atomicity (executescript auto-commits each statement otherwise)
    try:
        cursor = await db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='variables'"
        )
        row = await cursor.fetchone()
        if row and "'blueprint'" not in row["sql"]:
            # Need to recreate with new CHECK constraint
            await db.executescript("""
                BEGIN;
                CREATE TABLE IF NOT EXISTS variables_new (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT NOT NULL,
                    value       TEXT NOT NULL,
                    type        TEXT NOT NULL DEFAULT 'text' CHECK(type IN ('text', 'secret')),
                    scope       TEXT NOT NULL DEFAULT 'global' CHECK(scope IN ('global', 'agent', 'blueprint')),
                    agent_id    INTEGER REFERENCES agents(id),
                    description TEXT,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CHECK((scope = 'global' AND agent_id IS NULL) OR (scope IN ('agent', 'blueprint') AND agent_id IS NOT NULL))
                );
                INSERT OR IGNORE INTO variables_new SELECT * FROM variables;
                DROP TABLE variables;
                ALTER TABLE variables_new RENAME TO variables;
                COMMIT;
            """)
            # Recreate indexes dropped with the old table
            await db.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_variables_global_unique
                    ON variables(name) WHERE scope = 'global'
            """)
            await db.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_variables_agent_unique
                    ON variables(name, agent_id) WHERE scope = 'agent'
            """)
            await db.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Variables migration: {e}")

    # Migration: add indexed_messages to session_index_state
    try:
        await db.execute(
            "ALTER TABLE session_index_state ADD COLUMN indexed_messages INTEGER NOT NULL DEFAULT 0"
        )
        await db.commit()
    except Exception:
        pass  # Column already exists


async def close_db():
    global _db
    if _db is not None:
        await _db.close()
        _db = None


def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def get_or_create_agent(workspace_name: str) -> int:
    db = await get_db()
    cursor = await db.execute(
        "SELECT id FROM agents WHERE workspace_name = ?", (workspace_name,)
    )
    row = await cursor.fetchone()
    if row:
        return row["id"]
    cursor = await db.execute(
        "INSERT INTO agents (workspace_name) VALUES (?)", (workspace_name,)
    )
    await db.commit()
    return cursor.lastrowid


async def get_next_version_num(agent_id: int, file_path: str) -> int:
    db = await get_db()
    cursor = await db.execute(
        "SELECT MAX(version_num) as max_ver FROM file_versions WHERE agent_id = ? AND file_path = ?",
        (agent_id, file_path),
    )
    row = await cursor.fetchone()
    current = row["max_ver"] if row and row["max_ver"] is not None else 0
    return current + 1


async def create_version(
    agent_id: int,
    file_path: str,
    content: str,
    content_hash: str,
    source: str,
    likely_openclaw: bool = False,
    commit_msg: str | None = None,
) -> dict:
    db = await get_db()
    version_num = await get_next_version_num(agent_id, file_path)
    cursor = await db.execute(
        """INSERT INTO file_versions
           (agent_id, file_path, version_num, content, content_hash, source, likely_openclaw, commit_msg)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (agent_id, file_path, version_num, content, content_hash, source, likely_openclaw, commit_msg),
    )
    await db.commit()
    return {
        "id": cursor.lastrowid,
        "agent_id": agent_id,
        "file_path": file_path,
        "version_num": version_num,
        "content_hash": content_hash,
        "source": source,
        "likely_openclaw": likely_openclaw,
        "commit_msg": commit_msg,
        "ai_summary": None,
    }


async def get_versions(agent_id: int, file_path: str, limit: int = 20, offset: int = 0) -> tuple[list[dict], int]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM file_versions WHERE agent_id = ? AND file_path = ?",
        (agent_id, file_path),
    )
    row = await cursor.fetchone()
    total = row["cnt"]

    cursor = await db.execute(
        """SELECT id, version_num, source, likely_openclaw, commit_msg, ai_summary, created_at
           FROM file_versions
           WHERE agent_id = ? AND file_path = ?
           ORDER BY version_num DESC
           LIMIT ? OFFSET ?""",
        (agent_id, file_path, limit, offset),
    )
    rows = await cursor.fetchall()
    versions = [dict(r) for r in rows]
    return versions, total


async def get_version(version_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, agent_id, file_path, version_num, content, content_hash,
                  source, likely_openclaw, commit_msg, ai_summary, created_at
           FROM file_versions WHERE id = ?""",
        (version_id,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_previous_version(agent_id: int, file_path: str, version_num: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, agent_id, file_path, version_num, content, content_hash,
                  source, likely_openclaw, commit_msg, ai_summary, created_at
           FROM file_versions
           WHERE agent_id = ? AND file_path = ? AND version_num < ?
           ORDER BY version_num DESC LIMIT 1""",
        (agent_id, file_path, version_num),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def update_summary(version_id: int, summary: str):
    db = await get_db()
    await db.execute(
        "UPDATE file_versions SET ai_summary = ? WHERE id = ?",
        (summary, version_id),
    )
    await db.commit()


async def get_tracked_file(agent_id: int, file_path: str) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT agent_id, file_path, current_hash, last_scanned FROM tracked_files WHERE agent_id = ? AND file_path = ?",
        (agent_id, file_path),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def upsert_tracked_file(agent_id: int, file_path: str, current_hash: str):
    db = await get_db()
    await db.execute(
        """INSERT INTO tracked_files (agent_id, file_path, current_hash, last_scanned)
           VALUES (?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(agent_id, file_path)
           DO UPDATE SET current_hash = excluded.current_hash, last_scanned = CURRENT_TIMESTAMP""",
        (agent_id, file_path, current_hash),
    )
    await db.commit()


async def get_all_tracked_files(agent_id: int) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT agent_id, file_path, current_hash, last_scanned FROM tracked_files WHERE agent_id = ?",
        (agent_id,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Variable CRUD
# ---------------------------------------------------------------------------


async def list_variables(scope: str = None, agent_id: int = None) -> list[dict]:
    """List variables, optionally filtered by scope and/or agent_id."""
    db = await get_db()
    if scope in ("agent", "blueprint") and agent_id is not None:
        cursor = await db.execute(
            "SELECT * FROM variables WHERE scope = ? AND agent_id = ? ORDER BY name",
            (scope, agent_id),
        )
    elif scope == "global":
        cursor = await db.execute(
            "SELECT * FROM variables WHERE scope = 'global' ORDER BY name"
        )
    else:
        cursor = await db.execute("SELECT * FROM variables ORDER BY scope, name")
    return [dict(row) for row in await cursor.fetchall()]


async def get_variable(variable_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM variables WHERE id = ?", (variable_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def create_variable(name: str, value: str, var_type: str = "text",
                          scope: str = "global", agent_id: int = None,
                          description: str = None) -> dict:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO variables (name, value, type, scope, agent_id, description)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (name, value, var_type, scope, agent_id, description),
    )
    await db.commit()
    return await get_variable(cursor.lastrowid)


async def update_variable(variable_id: int, **fields) -> dict | None:
    db = await get_db()
    sets = []
    vals = []
    for key in ("name", "value", "type", "scope", "agent_id", "description"):
        if key in fields:
            sets.append(f"{key} = ?")
            vals.append(fields[key])
    if not sets:
        return await get_variable(variable_id)
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(variable_id)
    await db.execute(
        f"UPDATE variables SET {', '.join(sets)} WHERE id = ?", vals
    )
    await db.commit()
    return await get_variable(variable_id)


async def delete_variable(variable_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute("DELETE FROM variables WHERE id = ?", (variable_id,))
    await db.commit()
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Template CRUD
# ---------------------------------------------------------------------------


async def get_template(template_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_template_by_path(agent_id: int, file_path: str) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM templates WHERE agent_id = ? AND file_path = ?",
        (agent_id, file_path),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def list_templates(agent_id: int = None) -> list[dict]:
    db = await get_db()
    if agent_id is not None:
        cursor = await db.execute(
            "SELECT * FROM templates WHERE agent_id = ? ORDER BY file_path",
            (agent_id,),
        )
    else:
        cursor = await db.execute("SELECT * FROM templates ORDER BY agent_id, file_path")
    return [dict(row) for row in await cursor.fetchall()]


async def create_template(agent_id: int, file_path: str, content: str,
                          base_template_id: int = None) -> dict:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO templates (agent_id, file_path, content, base_template_id)
           VALUES (?, ?, ?, ?)""",
        (agent_id, file_path, content, base_template_id),
    )
    await db.commit()
    return await get_template(cursor.lastrowid)


async def update_template(template_id: int, content: str) -> dict | None:
    db = await get_db()
    await db.execute(
        "UPDATE templates SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (content, template_id),
    )
    await db.commit()
    return await get_template(template_id)


async def delete_template(template_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute("DELETE FROM templates WHERE id = ?", (template_id,))
    await db.commit()
    return cursor.rowcount > 0


async def delete_template_by_path(agent_id: int, file_path: str) -> bool:
    """Delete a template record by agent_id and file_path."""
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM templates WHERE agent_id = ? AND file_path = ?",
        (agent_id, file_path),
    )
    await db.commit()
    return cursor.rowcount > 0


async def find_templates_referencing_variable(var_name: str) -> list[dict]:
    """Find all templates whose content contains !{var_name}."""
    db = await get_db()
    pattern = f"!{{{var_name}}}"
    cursor = await db.execute(
        """SELECT t.*, a.workspace_name as agent_workspace_name
           FROM templates t
           JOIN agents a ON t.agent_id = a.id
           WHERE t.content LIKE ?
           ORDER BY a.workspace_name, t.file_path""",
        (f"%{pattern}%",),
    )
    return [dict(row) for row in await cursor.fetchall()]


# ---------------------------------------------------------------------------
# Virtual Agent helper
# ---------------------------------------------------------------------------


async def get_or_create_virtual_agent(workspace_name: str) -> int:
    """Get or create a virtual agent record (for blueprints)."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT id FROM agents WHERE workspace_name = ?", (workspace_name,)
    )
    row = await cursor.fetchone()
    if row:
        return row["id"]
    cursor = await db.execute(
        "INSERT INTO agents (workspace_name, is_virtual) VALUES (?, TRUE)",
        (workspace_name,),
    )
    await db.commit()
    return cursor.lastrowid


# ---------------------------------------------------------------------------
# Blueprint CRUD
# ---------------------------------------------------------------------------


async def create_blueprint(name: str, description: str, agent_id: int,
                           parent_id: int = None) -> dict:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO agent_blueprints (name, description, agent_id, parent_id)
           VALUES (?, ?, ?, ?)""",
        (name, description, agent_id, parent_id),
    )
    await db.commit()
    return await get_blueprint(cursor.lastrowid)


async def get_blueprint(blueprint_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM agent_blueprints WHERE id = ?", (blueprint_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_blueprint_by_agent_id(agent_id: int) -> dict | None:
    """Get blueprint that owns this virtual agent_id."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM agent_blueprints WHERE agent_id = ?", (agent_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def list_blueprints() -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT b.*, COUNT(d.id) as derivation_count
           FROM agent_blueprints b
           LEFT JOIN agent_derivations d ON d.blueprint_id = b.id
           GROUP BY b.id
           ORDER BY b.name"""
    )
    return [dict(row) for row in await cursor.fetchall()]


async def update_blueprint(blueprint_id: int, **fields) -> dict | None:
    db = await get_db()
    sets = []
    vals = []
    for key in ("name", "description"):
        if key in fields:
            sets.append(f"{key} = ?")
            vals.append(fields[key])
    if not sets:
        return await get_blueprint(blueprint_id)
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(blueprint_id)
    await db.execute(
        f"UPDATE agent_blueprints SET {', '.join(sets)} WHERE id = ?", vals
    )
    await db.commit()
    return await get_blueprint(blueprint_id)


async def delete_blueprint(blueprint_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM agent_blueprints WHERE id = ?", (blueprint_id,)
    )
    await db.commit()
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Derivation CRUD
# ---------------------------------------------------------------------------


async def create_derivation(blueprint_id: int, agent_id: int) -> dict:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO agent_derivations (blueprint_id, agent_id) VALUES (?, ?)",
        (blueprint_id, agent_id),
    )
    await db.commit()
    return await get_derivation(cursor.lastrowid)


async def get_derivation(derivation_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM agent_derivations WHERE id = ?", (derivation_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_derivation_by_agent_id(agent_id: int) -> dict | None:
    """Check if an agent is derived from a blueprint."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM agent_derivations WHERE agent_id = ?", (agent_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def list_derivations(blueprint_id: int) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT d.*, a.workspace_name
           FROM agent_derivations d
           JOIN agents a ON d.agent_id = a.id
           WHERE d.blueprint_id = ?
           ORDER BY d.created_at""",
        (blueprint_id,),
    )
    return [dict(row) for row in await cursor.fetchall()]


# ---------------------------------------------------------------------------
# Override CRUD
# ---------------------------------------------------------------------------


async def add_override(derivation_id: int, file_path: str) -> dict:
    db = await get_db()
    cursor = await db.execute(
        """INSERT OR IGNORE INTO derivation_overrides (derivation_id, file_path)
           VALUES (?, ?)""",
        (derivation_id, file_path),
    )
    await db.commit()
    return {"derivation_id": derivation_id, "file_path": file_path}


async def remove_override(derivation_id: int, file_path: str) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM derivation_overrides WHERE derivation_id = ? AND file_path = ?",
        (derivation_id, file_path),
    )
    await db.commit()
    return cursor.rowcount > 0


async def clear_all_overrides(derivation_id: int) -> int:
    """Remove ALL override records for a derivation. Returns count deleted."""
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM derivation_overrides WHERE derivation_id = ?",
        (derivation_id,),
    )
    await db.commit()
    return cursor.rowcount


async def list_overrides(derivation_id: int) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM derivation_overrides WHERE derivation_id = ? ORDER BY file_path",
        (derivation_id,),
    )
    return [dict(row) for row in await cursor.fetchall()]


async def is_file_overridden(derivation_id: int, file_path: str) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "SELECT 1 FROM derivation_overrides WHERE derivation_id = ? AND file_path = ?",
        (derivation_id, file_path),
    )
    return await cursor.fetchone() is not None


async def delete_derivations_for_blueprint(blueprint_id: int) -> int:
    """Delete all derivation records (and their overrides) for a blueprint."""
    db = await get_db()
    # First get all derivation ids
    cursor = await db.execute(
        "SELECT id FROM agent_derivations WHERE blueprint_id = ?", (blueprint_id,)
    )
    derivation_ids = [row["id"] for row in await cursor.fetchall()]
    if not derivation_ids:
        return 0
    # Delete overrides for all derivations
    placeholders = ",".join("?" * len(derivation_ids))
    await db.execute(
        f"DELETE FROM derivation_overrides WHERE derivation_id IN ({placeholders})",
        derivation_ids,
    )
    # Then delete derivations
    cursor = await db.execute(
        "DELETE FROM agent_derivations WHERE blueprint_id = ?", (blueprint_id,)
    )
    await db.commit()
    return cursor.rowcount


# ---------------------------------------------------------------------------
# Blueprint Pending Changes CRUD
# ---------------------------------------------------------------------------

async def upsert_pending_change(
    blueprint_id: int, file_path: str, change_type: str,
    old_content: str | None, new_content: str | None,
    old_hash: str | None, new_hash: str | None,
) -> dict | None:
    """Create or update a pending change record.

    Returns None if the change was previously rejected with the same new_hash
    (prevents rejected changes from reappearing on the next scan cycle).
    """
    db = await get_db()
    cursor = await db.execute(
        "SELECT id FROM blueprint_pending_changes WHERE blueprint_id = ? AND file_path = ? AND status = 'pending'",
        (blueprint_id, file_path),
    )
    existing = await cursor.fetchone()

    if existing:
        await db.execute(
            """UPDATE blueprint_pending_changes
               SET change_type = ?, old_content = ?, new_content = ?,
                   old_hash = ?, new_hash = ?, detected_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (change_type, old_content, new_content, old_hash, new_hash, existing["id"]),
        )
        await db.commit()
        change_id = existing["id"]
    else:
        # Skip if this exact change was already rejected (same blueprint, file, new_hash).
        # Use IS NULL-safe comparison because new_hash can be None (deleted files).
        if new_hash is None:
            rejected = await db.execute(
                """SELECT id FROM blueprint_pending_changes
                   WHERE blueprint_id = ? AND file_path = ? AND status = 'rejected' AND new_hash IS NULL""",
                (blueprint_id, file_path),
            )
        else:
            rejected = await db.execute(
                """SELECT id FROM blueprint_pending_changes
                   WHERE blueprint_id = ? AND file_path = ? AND status = 'rejected' AND new_hash = ?""",
                (blueprint_id, file_path, new_hash),
            )
        if await rejected.fetchone():
            return None  # Already rejected, don't re-create

        cursor = await db.execute(
            """INSERT INTO blueprint_pending_changes
               (blueprint_id, file_path, change_type, old_content, new_content, old_hash, new_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (blueprint_id, file_path, change_type, old_content, new_content, old_hash, new_hash),
        )
        await db.commit()
        change_id = cursor.lastrowid

    cursor = await db.execute("SELECT * FROM blueprint_pending_changes WHERE id = ?", (change_id,))
    return dict(await cursor.fetchone())


async def delete_pending_change_by_file(blueprint_id: int, file_path: str) -> bool:
    """Delete pending change for a specific file."""
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM blueprint_pending_changes WHERE blueprint_id = ? AND file_path = ? AND status = 'pending'",
        (blueprint_id, file_path),
    )
    await db.commit()
    return cursor.rowcount > 0


async def get_pending_change(change_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM blueprint_pending_changes WHERE id = ?", (change_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def list_pending_changes(blueprint_id: int | None = None) -> list[dict]:
    """List pending changes. If blueprint_id given, filter to that blueprint."""
    db = await get_db()
    if blueprint_id is not None:
        cursor = await db.execute(
            "SELECT * FROM blueprint_pending_changes WHERE blueprint_id = ? AND status = 'pending' ORDER BY detected_at",
            (blueprint_id,),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM blueprint_pending_changes WHERE status = 'pending' ORDER BY detected_at",
        )
    return [dict(r) for r in await cursor.fetchall()]


async def get_pending_changes_summary() -> list[dict]:
    """Get per-blueprint pending change counts."""
    db = await get_db()
    cursor = await db.execute("""
        SELECT pc.blueprint_id, bp.name AS blueprint_name,
               COUNT(*) AS pending_count,
               MAX(pc.detected_at) AS latest_detected_at
        FROM blueprint_pending_changes pc
        JOIN agent_blueprints bp ON bp.id = pc.blueprint_id
        WHERE pc.status = 'pending'
        GROUP BY pc.blueprint_id
    """)
    return [dict(r) for r in await cursor.fetchall()]


async def resolve_pending_change(change_id: int, status: str) -> bool:
    """Mark a pending change as accepted or rejected."""
    if status not in ("accepted", "rejected"):
        raise ValueError(f"Invalid status: {status}")
    db = await get_db()
    cursor = await db.execute(
        "UPDATE blueprint_pending_changes SET status = ?, resolved_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'pending'",
        (status, change_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def delete_pending_changes_for_blueprint(blueprint_id: int) -> int:
    """Delete all pending changes for a blueprint (used on blueprint deletion)."""
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM blueprint_pending_changes WHERE blueprint_id = ?",
        (blueprint_id,),
    )
    await db.commit()
    return cursor.rowcount


# ---------------------------------------------------------------------------
# Agent Pending Changes CRUD
# ---------------------------------------------------------------------------

async def upsert_agent_pending_change(
    agent_id: int, file_path: str, change_type: str,
    old_content: str | None, new_content: str | None,
    old_hash: str | None, new_hash: str | None,
) -> dict | None:
    """Create or update an agent pending change.

    Returns None if the change was previously rejected with the same new_hash.
    """
    db = await get_db()
    cursor = await db.execute(
        "SELECT id FROM agent_pending_changes WHERE agent_id = ? AND file_path = ? AND status = 'pending'",
        (agent_id, file_path),
    )
    existing = await cursor.fetchone()

    if existing:
        await db.execute(
            """UPDATE agent_pending_changes
               SET change_type = ?, old_content = ?, new_content = ?,
                   old_hash = ?, new_hash = ?, detected_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (change_type, old_content, new_content, old_hash, new_hash, existing["id"]),
        )
        await db.commit()
        change_id = existing["id"]
    else:
        rejected = await db.execute(
            """SELECT id FROM agent_pending_changes
               WHERE agent_id = ? AND file_path = ? AND status = 'rejected' AND new_hash = ?""",
            (agent_id, file_path, new_hash),
        )
        if await rejected.fetchone():
            return None

        cursor = await db.execute(
            """INSERT INTO agent_pending_changes
               (agent_id, file_path, change_type, old_content, new_content, old_hash, new_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (agent_id, file_path, change_type, old_content, new_content, old_hash, new_hash),
        )
        await db.commit()
        change_id = cursor.lastrowid

    cursor = await db.execute("SELECT * FROM agent_pending_changes WHERE id = ?", (change_id,))
    return dict(await cursor.fetchone())


async def delete_agent_pending_change_by_file(agent_id: int, file_path: str) -> bool:
    """Delete pending agent change for a specific file."""
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM agent_pending_changes WHERE agent_id = ? AND file_path = ? AND status = 'pending'",
        (agent_id, file_path),
    )
    await db.commit()
    return cursor.rowcount > 0


async def get_agent_pending_change(change_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM agent_pending_changes WHERE id = ?", (change_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def list_agent_pending_changes(agent_id: int) -> list[dict]:
    """List pending changes for an agent."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM agent_pending_changes WHERE agent_id = ? AND status = 'pending' ORDER BY detected_at",
        (agent_id,),
    )
    return [dict(r) for r in await cursor.fetchall()]


async def resolve_agent_pending_change(change_id: int, status: str) -> bool:
    """Mark an agent pending change as accepted or rejected."""
    if status not in ("accepted", "rejected"):
        raise ValueError(f"Invalid status: {status}")
    db = await get_db()
    cursor = await db.execute(
        "UPDATE agent_pending_changes SET status = ?, resolved_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'pending'",
        (status, change_id),
    )
    await db.commit()
    return cursor.rowcount > 0
