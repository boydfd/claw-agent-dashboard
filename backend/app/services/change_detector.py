"""Change detector — abstract interface + hash-based scanning implementation."""
import asyncio
import os
from abc import ABC, abstractmethod
from pathlib import Path

from ..config import AGENTS_DIR, SESSION_DATA_DIR, resolve_agent_dir
from ..services import version_db, version_service
from ..services.file_service import CORE_FILES
from ..services.scanner import list_agents
from ..services.version_db import MAX_SCAN_FILE_SIZE
from ..services.config import read_config

BINARY_EXTENSIONS = {
    '.tar', '.gz', '.tgz', '.zip', '.bz2', '.xz', '.7z',
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp',
    '.woff', '.woff2', '.ttf', '.eot',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx',
    '.exe', '.dll', '.so', '.dylib', '.o', '.a',
    '.pyc', '.pyo', '.class', '.jar',
    '.sqlite', '.db', '.sqlite3',
    '.mp3', '.mp4', '.wav', '.avi', '.mov',
}


def _should_skip_file(path: Path) -> bool:
    """Return True if the file should be skipped (binary, too large, or missing)."""
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    try:
        if path.stat().st_size > MAX_SCAN_FILE_SIZE:
            return True
    except OSError:
        return True
    return False


class ChangeDetector(ABC):
    @abstractmethod
    async def start(self):
        ...

    @abstractmethod
    async def stop(self):
        ...


class HashScanDetector(ChangeDetector):
    """Periodic hash-based file change detection."""

    def __init__(self, interval: int = 30):
        self._interval = interval
        self._task: asyncio.Task | None = None
        self._running = False

    def _get_excluded_dirs(self) -> set[str]:
        config = read_config()
        excluded = config.get("change_detector", {}).get("excluded_dirs", [])
        if not isinstance(excluded, list):
            return set()
        return {str(item) for item in excluded if str(item).strip()}

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._scan_loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _scan_loop(self):
        while self._running:
            try:
                await self._scan_all()
            except Exception as e:
                print(f"[change_detector] Scan error: {e}")
            await asyncio.sleep(self._interval)

    async def _scan_all(self):
        from ..services.template_engine import render_template

        agents = list_agents()
        for agent in agents:
            agent_name = agent["name"]
            agent_dir = Path(AGENTS_DIR) / resolve_agent_dir(agent_name)
            if not agent_dir.exists():
                continue

            agent_id = await version_db.get_or_create_agent(agent_name)
            tracked = await version_db.get_all_tracked_files(agent_id)
            tracked_map = {t["file_path"]: t["current_hash"] for t in tracked}
            excluded_dirs = self._get_excluded_dirs()

            # Collect managed files: core files + all non-hidden top-level
            # files + known managed subdirectories (skills/, docker/).
            # Excludes user-data dirs like develops/, memory/, backup/.
            MANAGED_SUBDIRS = {"skills", "docker"}
            managed_files = []
            for fname in CORE_FILES:
                fpath = agent_dir / fname
                if fpath.exists() and fpath.is_file():
                    managed_files.append((fname, fpath))
            core_set = set(CORE_FILES)
            for fpath in agent_dir.iterdir():
                if fpath.name.startswith('.'):
                    continue
                if fpath.is_file() and fpath.name not in core_set:
                    managed_files.append((fpath.name, fpath))
                elif fpath.is_dir() and fpath.name in MANAGED_SUBDIRS:
                    for root, dirs, files in os.walk(fpath):
                        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in excluded_dirs]
                        for fname in files:
                            if fname.startswith('.'): 
                                continue
                            full_path = Path(root) / fname
                            rel_path = str(full_path.relative_to(agent_dir))
                            if any(part in excluded_dirs for part in Path(rel_path).parts):
                                continue
                            managed_files.append((rel_path, full_path))

            # Look up derivation info once per agent
            derivation = await version_db.get_derivation_by_agent_id(agent_id)
            blueprint_agent_id = None
            if derivation:
                bp = await version_db.get_blueprint(derivation["blueprint_id"])
                if bp:
                    blueprint_agent_id = bp["agent_id"]

            seen_paths = set()
            for rel_path, full_path in managed_files:
                seen_paths.add(rel_path)
                if _should_skip_file(full_path):
                    continue
                try:
                    content = full_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue

                content_hash = version_db.compute_hash(content)

                if rel_path in tracked_map:
                    if content_hash != tracked_map[rel_path]:
                        # Hash changed — check template
                        await self._handle_file_change(
                            agent_id, agent_name, rel_path, content, content_hash,
                            derivation, blueprint_agent_id,
                        )
                else:
                    # New file — create initial version + tracked entry
                    await version_db.create_version(
                        agent_id=agent_id, file_path=rel_path,
                        content=content, content_hash=content_hash,
                        source="external",
                    )
                    await version_db.upsert_tracked_file(agent_id, rel_path, content_hash)

        await self._scan_blueprints()

    async def _handle_file_change(
        self, agent_id, agent_name, file_path, disk_content, disk_hash,
        derivation, blueprint_agent_id,
    ):
        """Handle a detected file change: create pending change or record version."""
        from ..services.template_engine import render_template
        from ..services import variable_service

        # Look up template via full chain: agent-own → blueprint inherited
        template = await version_db.get_template_by_path(agent_id, file_path)
        if not template and derivation and blueprint_agent_id:
            template = await version_db.get_template_by_path(blueprint_agent_id, file_path)

        if template:
            # Render template with correct variable scope
            if derivation and blueprint_agent_id:
                variables = await variable_service.get_raw_variables_for_derived_agent(
                    agent_id, blueprint_agent_id
                )
            else:
                variables = await variable_service.get_raw_variables_for_agent(agent_id)

            result = render_template(template["content"], variables)
            rendered_content = result.content

            if disk_content == rendered_content:
                # Disk matches template — clear any pending change
                await version_db.delete_agent_pending_change_by_file(agent_id, file_path)
            else:
                # Disk differs from template — create pending change
                rendered_hash = version_db.compute_hash(rendered_content)
                await version_db.upsert_agent_pending_change(
                    agent_id=agent_id, file_path=file_path,
                    change_type="modified",
                    old_content=rendered_content, new_content=disk_content,
                    old_hash=rendered_hash, new_hash=disk_hash,
                )

            # Update tracked hash so detector won't re-process next cycle
            await version_db.upsert_tracked_file(agent_id, file_path, disk_hash)
        else:
            # No template — lazy-load: record version directly
            likely_openclaw = self._check_likely_openclaw(agent_name)
            await version_service.record_external_change(
                agent_id=agent_id, file_path=file_path,
                content=disk_content, content_hash=disk_hash,
                likely_openclaw=likely_openclaw,
            )

    async def _scan_blueprints(self):
        """Scan blueprint directories, compare against DB templates."""
        from ..config import BLUEPRINTS_DIR

        blueprints_dir = Path(BLUEPRINTS_DIR)
        if not blueprints_dir.exists():
            return

        all_blueprints = await version_db.list_blueprints()
        bp_by_dir = {bp["name"]: bp for bp in all_blueprints}

        for dir_entry in blueprints_dir.iterdir():
            if not dir_entry.is_dir() or dir_entry.name.startswith('.'):
                continue

            bp = bp_by_dir.get(dir_entry.name)
            if not bp:
                continue

            db_templates = await version_db.list_templates(agent_id=bp["agent_id"])
            db_map = {t["file_path"]: t for t in db_templates}

            disk_files = self._collect_blueprint_files(dir_entry)
            seen_paths = set()

            for rel_path, full_path in disk_files:
                seen_paths.add(rel_path)
                if _should_skip_file(full_path):
                    continue
                try:
                    content = full_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                content_hash = version_db.compute_hash(content)

                if rel_path in db_map:
                    db_hash = version_db.compute_hash(db_map[rel_path]["content"])
                    if content_hash != db_hash:
                        await self._upsert_pending_change(
                            bp["id"], rel_path, "modified",
                            old_content=db_map[rel_path]["content"],
                            new_content=content,
                        )
                    else:
                        # File matches DB — clear any stale pending change
                        await version_db.delete_pending_change_by_file(bp["id"], rel_path)
                else:
                    await self._upsert_pending_change(
                        bp["id"], rel_path, "added",
                        old_content=None, new_content=content,
                    )

            for db_path in db_map:
                if db_path not in seen_paths:
                    await self._upsert_pending_change(
                        bp["id"], db_path, "deleted",
                        old_content=db_map[db_path]["content"],
                        new_content=None,
                    )

    def _collect_blueprint_files(self, bp_dir: Path) -> list[tuple[str, Path]]:
        """Collect managed files from a blueprint directory.

        Scans all top-level files and recursively walks all subdirectories
        (skills/, docker/, etc.), skipping hidden directories (dot-prefixed).
        """
        files = []
        excluded_dirs = self._get_excluded_dirs()
        for f in bp_dir.iterdir():
            if f.name.startswith('.'):
                continue
            if f.is_file():
                files.append((f.name, f))
            elif f.is_dir():
                if f.name in excluded_dirs:
                    continue
                for root, dirs, filenames in os.walk(f):
                    # Skip hidden subdirectories
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in excluded_dirs]
                    for fname in filenames:
                        if fname.startswith('.'):
                            continue
                        full = Path(root) / fname
                        rel = str(full.relative_to(bp_dir))
                        if any(part in excluded_dirs for part in Path(rel).parts):
                            continue
                        files.append((rel, full))
        return files

    async def _upsert_pending_change(
        self, blueprint_id: int, file_path: str, change_type: str,
        old_content: str | None, new_content: str | None,
    ):
        """Create or update a pending change record."""
        old_hash = version_db.compute_hash(old_content) if old_content else None
        new_hash = version_db.compute_hash(new_content) if new_content else None

        if old_hash == new_hash:
            await version_db.delete_pending_change_by_file(blueprint_id, file_path)
            return

        await version_db.upsert_pending_change(
            blueprint_id=blueprint_id, file_path=file_path,
            change_type=change_type, old_content=old_content,
            new_content=new_content, old_hash=old_hash, new_hash=new_hash,
        )

    def _check_likely_openclaw(self, agent_name: str) -> bool:
        """Heuristic: check if any .jsonl.lock files exist for this agent."""
        # OpenClaw session data path
        short_name = agent_name.replace("workspace-", "")
        session_dir = Path(SESSION_DATA_DIR) / f"agents/{short_name}"
        if not session_dir.exists():
            # Try alternate path structure
            session_dir = Path(SESSION_DATA_DIR) / short_name
        if not session_dir.exists():
            return False

        try:
            for entry in session_dir.iterdir():
                if entry.name.endswith(".jsonl.lock"):
                    return True
        except Exception:
            pass
        return False


# Module-level singleton
_detector: ChangeDetector | None = None


async def start_detector(interval: int = 30):
    global _detector
    _detector = HashScanDetector(interval=interval)
    await _detector.start()


async def stop_detector():
    global _detector
    if _detector:
        await _detector.stop()
        _detector = None
