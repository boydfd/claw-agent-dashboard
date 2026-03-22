"""File service — reads files, detects language, builds file tree."""
import os
import asyncio
from pathlib import Path

from ..config import AGENTS_DIR, AGENTS_HOST_DIR, resolve_agent_dir

# Core files to surface (in display order)
CORE_FILES = [
    "SOUL.md", "USER.md", "AGENTS.md", "IDENTITY.md",
    "TOOLS.md", "HEARTBEAT.md", "BOOTSTRAP.md",
]

# Language detection by extension
LANG_MAP = {
    ".md": "markdown",
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascriptreact",
    ".tsx": "typescriptreact",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".html": "html",
    ".css": "css",
    ".sql": "sql",
    ".xml": "xml",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".txt": "plaintext",
    ".cfg": "ini",
    ".ini": "ini",
    ".env": "shell",
}


def _detect_language(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return LANG_MAP.get(ext, "plaintext")


def _agent_path(agent_name: str) -> Path:
    return Path(AGENTS_DIR) / resolve_agent_dir(agent_name)


def list_agent_files(agent_name: str) -> list[dict]:
    """List core .md files + other .md files in agent root."""
    agent_dir = _agent_path(agent_name)
    if not agent_dir.exists():
        return []

    result = []
    seen = set()

    # Core files first (in defined order)
    for fname in CORE_FILES:
        fpath = agent_dir / fname
        if fpath.exists():
            result.append({
                "name": fname,
                "path": fname,
                "type": "file",
                "is_core": True,
            })
            seen.add(fname)

    # Other .md files
    for fpath in sorted(agent_dir.iterdir()):
        if fpath.is_file() and fpath.suffix.lower() == ".md" and fpath.name not in seen:
            result.append({
                "name": fpath.name,
                "path": fpath.name,
                "type": "file",
                "is_core": False,
            })

    return result


# Directories to exclude from "Other Files"
EXCLUDED_DIRS = {"skills", "memory", "node_modules", ".git", "__pycache__", ".cache"}


def list_memory_files(agent_name: str) -> list[dict]:
    """List memory files (*.md) in agent's memory/ directory."""
    memory_dir = _agent_path(agent_name) / "memory"
    if not memory_dir.exists():
        return []

    result = []
    for fpath in sorted(memory_dir.iterdir(), reverse=True):  # newest first
        if fpath.is_file() and fpath.suffix.lower() == ".md":
            rel_path = f"memory/{fpath.name}"
            result.append({
                "name": fpath.name,
                "path": rel_path,
                "type": "file",
            })
    return result


def list_other_files(agent_name: str) -> list[dict]:
    """List files/directories in agent root, excluding core files, skills/, memory/, etc."""
    agent_dir = _agent_path(agent_name)
    if not agent_dir.exists():
        return []

    core_names = set(CORE_FILES)

    def _walk(directory: Path, rel_prefix: str) -> list[dict]:
        items = []
        try:
            for entry in sorted(directory.iterdir()):
                name = entry.name
                rel_path = f"{rel_prefix}/{name}" if rel_prefix else name

                # Root-level exclusions
                if not rel_prefix:
                    if name in core_names:
                        continue
                    if entry.is_dir() and name in EXCLUDED_DIRS:
                        continue
                    # .md files at root are already in Core Files section
                    if entry.is_file() and entry.suffix.lower() == ".md":
                        continue

                # Skip uninteresting dirs at any level
                if entry.is_dir() and name in {".git", "__pycache__", "node_modules", ".cache"}:
                    continue

                if entry.is_file():
                    items.append({
                        "name": name,
                        "path": rel_path,
                        "type": "file",
                    })
                elif entry.is_dir():
                    children = _walk(entry, rel_path)
                    items.append({
                        "name": name,
                        "path": rel_path,
                        "type": "directory",
                        "children": children,
                    })
        except PermissionError:
            pass
        return items

    return _walk(agent_dir, "")


def list_agent_skills(agent_name: str) -> list[dict]:
    """List skills in agent's skills/ directory."""
    skills_dir = _agent_path(agent_name) / "skills"
    if not skills_dir.exists():
        return []

    skills = []
    for entry in sorted(skills_dir.iterdir()):
        if entry.is_dir():
            # Try to get skill name from SKILL.md
            skill_md = entry / "SKILL.md"
            display_name = entry.name
            if skill_md.exists():
                try:
                    content = skill_md.read_text(encoding="utf-8", errors="replace")
                    for line in content.splitlines():
                        if line.startswith("name:"):
                            display_name = line.split(":", 1)[1].strip()
                            break
                except Exception:
                    pass

            skills.append({
                "name": entry.name,
                "display_name": display_name,
                "path": f"skills/{entry.name}",
            })
    return skills


def list_skill_files(agent_name: str, skill_name: str) -> list[dict]:
    """Recursively list all files in a skill directory."""
    skill_dir = _agent_path(agent_name) / "skills" / skill_name
    if not skill_dir.exists():
        return []

    def _walk(directory: Path, rel_prefix: str) -> list[dict]:
        items = []
        for entry in sorted(directory.iterdir()):
            rel_path = f"{rel_prefix}/{entry.name}" if rel_prefix else entry.name
            full_rel = f"skills/{skill_name}/{rel_path}"
            if entry.is_file():
                items.append({
                    "name": entry.name,
                    "path": full_rel,
                    "type": "file",
                })
            elif entry.is_dir():
                children = _walk(entry, rel_path)
                items.append({
                    "name": entry.name,
                    "path": full_rel,
                    "type": "directory",
                    "children": children,
                })
        return items

    return _walk(skill_dir, "")


def list_all_agent_files(agent_name: str) -> list[dict]:
    """Recursively list ALL files in an agent workspace as a flat list.
    Returns [{"path": "relative/path", "content": "..."}].
    Skips .git, __pycache__, node_modules, .cache directories."""
    agent_dir = _agent_path(agent_name)
    if not agent_dir.exists():
        return []

    skip_dirs = {".git", "__pycache__", "node_modules", ".cache"}
    result = []

    for root, dirs, files in os.walk(agent_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in sorted(files):
            fpath = Path(root) / fname
            rel_path = str(fpath.relative_to(agent_dir))
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            result.append({
                "path": rel_path,
                "content": content,
            })

    return result


def write_file(agent_name: str, rel_path: str, content: str) -> dict:
    """Write content back to the original file. DANGEROUS — overwrites the real file."""
    agent_dir = _agent_path(agent_name)
    file_path = agent_dir / rel_path

    # Security: ensure path doesn't escape agent directory
    try:
        file_path = file_path.resolve()
        agent_dir_resolved = agent_dir.resolve()
        if not str(file_path).startswith(str(agent_dir_resolved)):
            raise PermissionError("Path traversal not allowed")
    except PermissionError:
        raise
    except Exception:
        raise ValueError(f"Invalid path: {rel_path}")

    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"File not found: {rel_path}")

    file_path.write_text(content, encoding="utf-8")

    host_path = str(Path(AGENTS_HOST_DIR) / resolve_agent_dir(agent_name) / rel_path)
    return {
        "path": rel_path,
        "name": file_path.name,
        "host_path": host_path,
        "saved": True,
    }


def create_file(agent_name: str, rel_path: str, content: str) -> dict:
    """Create a new file in the agent workspace (supports non-existing paths).
    Creates parent directories as needed. Used by derive flow."""
    agent_dir = _agent_path(agent_name)

    # Ensure agent directory exists
    agent_dir.mkdir(parents=True, exist_ok=True)

    file_path = agent_dir / rel_path

    # Security: ensure path doesn't escape agent directory
    try:
        file_path = file_path.resolve()
        agent_dir_resolved = agent_dir.resolve()
        if not str(file_path).startswith(str(agent_dir_resolved)):
            raise PermissionError("Path traversal not allowed")
    except PermissionError:
        raise
    except Exception:
        raise ValueError(f"Invalid path: {rel_path}")

    # Create parent directories
    file_path.parent.mkdir(parents=True, exist_ok=True)

    file_path.write_text(content, encoding="utf-8")

    host_path = str(Path(AGENTS_HOST_DIR) / resolve_agent_dir(agent_name) / rel_path)
    return {
        "path": rel_path,
        "name": file_path.name,
        "host_path": host_path,
        "created": True,
    }


def delete_file(agent_name: str, rel_path: str) -> bool:
    """Delete a file from the agent workspace."""
    agent_dir = _agent_path(agent_name)
    file_path = agent_dir / rel_path

    # Security: ensure path doesn't escape agent directory
    try:
        file_path = file_path.resolve()
        agent_dir_resolved = agent_dir.resolve()
        if not str(file_path).startswith(str(agent_dir_resolved)):
            raise PermissionError("Path traversal not allowed")
    except PermissionError:
        raise
    except Exception:
        raise ValueError(f"Invalid path: {rel_path}")

    if file_path.exists() and file_path.is_file():
        file_path.unlink()
        return True
    return False


def read_file(agent_name: str, rel_path: str) -> dict | None:
    """Read a file and return its content with metadata."""
    agent_dir = _agent_path(agent_name)
    file_path = agent_dir / rel_path

    # Security: ensure path doesn't escape agent directory
    try:
        file_path = file_path.resolve()
        agent_dir_resolved = agent_dir.resolve()
        if not str(file_path).startswith(str(agent_dir_resolved)):
            return None
    except Exception:
        return None

    if not file_path.exists() or not file_path.is_file():
        return None

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    host_path = str(Path(AGENTS_HOST_DIR) / resolve_agent_dir(agent_name) / rel_path)

    return {
        "path": rel_path,
        "name": file_path.name,
        "content": content,
        "language": _detect_language(file_path.name),
        "host_path": host_path,
    }


# --- Async wrappers (for use in route handlers) ---

async def list_agent_files_async(agent_name: str) -> list[dict]:
    return await asyncio.to_thread(list_agent_files, agent_name)

async def list_memory_files_async(agent_name: str) -> list[dict]:
    return await asyncio.to_thread(list_memory_files, agent_name)

async def list_other_files_async(agent_name: str) -> list[dict]:
    return await asyncio.to_thread(list_other_files, agent_name)

async def list_agent_skills_async(agent_name: str) -> list[dict]:
    return await asyncio.to_thread(list_agent_skills, agent_name)

async def list_skill_files_async(agent_name: str, skill_name: str) -> list[dict]:
    return await asyncio.to_thread(list_skill_files, agent_name, skill_name)

async def read_file_async(agent_name: str, rel_path: str) -> dict | None:
    return await asyncio.to_thread(read_file, agent_name, rel_path)

async def write_file_async(agent_name: str, rel_path: str, content: str) -> dict:
    return await asyncio.to_thread(write_file, agent_name, rel_path, content)

async def create_file_async(agent_name: str, rel_path: str, content: str) -> dict:
    return await asyncio.to_thread(create_file, agent_name, rel_path, content)

async def delete_file_async(agent_name: str, rel_path: str) -> bool:
    return await asyncio.to_thread(delete_file, agent_name, rel_path)
