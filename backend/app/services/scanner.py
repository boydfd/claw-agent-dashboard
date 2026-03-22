"""Agent scanning service — discovers workspace-* directories."""
import os
import re
import asyncio
from pathlib import Path

from ..config import AGENTS_DIR, AGENTS_HOST_DIR


def _extract_display_name(agent_path: Path) -> str:
    """Try to extract a display name from IDENTITY.md, falling back to directory name."""
    identity_file = agent_path / "IDENTITY.md"
    if identity_file.exists():
        try:
            content = identity_file.read_text(encoding="utf-8", errors="replace")
            # Look for **Name:** field first (e.g. "- **Name:** 九歌 (Jiuge)")
            for line in content.splitlines():
                m = re.search(r"\*\*Name[：:]?\*\*[:\s]+(.+)", line)
                if m:
                    return m.group(1).strip()
            # Fallback: first H1 heading, skip "IDENTITY.md" style headers
            for line in content.splitlines():
                m = re.match(r"^#\s+(.+)", line)
                if m:
                    heading = m.group(1).strip()
                    if "IDENTITY" not in heading.upper():
                        return heading
            # Fallback: check SOUL.md for name
            soul_file = agent_path / "SOUL.md"
            if soul_file.exists():
                try:
                    soul = soul_file.read_text(encoding="utf-8", errors="replace")
                    for line in soul.splitlines():
                        m = re.search(r"\*\*Name[：:]?\*\*[:\s]+(.+)", line)
                        if m:
                            return m.group(1).strip()
                except Exception:
                    pass
        except Exception:
            pass
    # Fallback: prettify directory name
    return agent_path.name.replace("workspace-", "").replace("-", " ").title()


def list_agents() -> list[dict]:
    """Return list of discovered agents."""
    agents_dir = Path(AGENTS_DIR)
    if not agents_dir.exists():
        return []

    agents = []
    for entry in sorted(agents_dir.iterdir()):
        if entry.is_dir() and entry.name.startswith("workspace-"):
            agents.append({
                "name": entry.name,
                "display_name": _extract_display_name(entry),
                "path": str(entry),
                "host_path": str(Path(AGENTS_HOST_DIR) / entry.name),
            })

    # Include the main agent ("workspace" directory without a suffix)
    main_dir = agents_dir / "workspace"
    if main_dir.is_dir():
        agents.insert(0, {
            "name": "workspace-main",
            "display_name": _extract_display_name(main_dir),
            "path": str(main_dir),
            "host_path": str(Path(AGENTS_HOST_DIR) / "workspace"),
        })

    return agents


async def list_agents_async() -> list[dict]:
    """Async wrapper for list_agents — runs sync I/O in a thread."""
    return await asyncio.to_thread(list_agents)
