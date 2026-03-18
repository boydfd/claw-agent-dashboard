"""OpenClaw service — openclaw.json manipulation and gateway restart."""
import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..config import OPENCLAW_CONFIG_PATH, AGENTS_HOST_DIR

logger = logging.getLogger(__name__)


async def register_agent(
    agent_name: str, workspace_name: str, talk_room: str | None = None
) -> dict:
    """Add agent to openclaw.json (agents.list + optional binding)."""
    config_path = Path(OPENCLAW_CONFIG_PATH)

    if not config_path.exists():
        raise FileNotFoundError(f"openclaw.json not found at {config_path}")

    # Read current config
    raw = config_path.read_text(encoding="utf-8")

    # Strip single-line comments for JSON5 compatibility
    lines = []
    for line in raw.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("//"):
            continue
        # Remove trailing comments — skip :// (URLs like http://...)
        idx = 0
        while True:
            comment_idx = line.find("//", idx)
            if comment_idx < 0:
                break
            # Skip :// (URL scheme)
            if comment_idx > 0 and line[comment_idx - 1] == ':':
                idx = comment_idx + 2
                continue
            # Only strip if no unmatched quote after //
            if '"' not in line[comment_idx:]:
                line = line[:comment_idx]
            break
        lines.append(line)
    clean_json = "\n".join(lines)

    try:
        config = json.loads(clean_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse openclaw.json: {e}")

    # Backup
    backup_path = config_path.with_suffix(".json.bak")
    shutil.copy2(str(config_path), str(backup_path))

    # Add to agents.list
    agents_list = config.get("agents", {}).get("list", [])
    workspace_path = str(Path(AGENTS_HOST_DIR) / workspace_name)

    # Check duplicate
    if any(a.get("id") == agent_name for a in agents_list):
        raise ValueError(f"Agent '{agent_name}' already exists in openclaw.json")

    agents_list.append({
        "id": agent_name,
        "workspace": workspace_path,
    })
    if "agents" not in config:
        config["agents"] = {}
    config["agents"]["list"] = agents_list

    # Add binding if talk_room provided
    if talk_room:
        bindings = config.get("bindings", [])
        bindings.append({
            "agentId": agent_name,
            "match": {
                "channel": "nextcloud-talk",
                "peer": {"kind": "group", "id": talk_room},
            },
        })
        config["bindings"] = bindings

    # Atomic write (write to temp, then rename)
    dir_path = config_path.parent
    fd, tmp_path = tempfile.mkstemp(dir=str(dir_path), suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_path, str(config_path))
    except Exception:
        os.unlink(tmp_path)
        raise

    return {"registered": True, "agent_name": agent_name}


async def restart_gateway() -> dict:
    """Run openclaw gateway restart."""
    try:
        result = subprocess.run(
            ["openclaw", "gateway", "restart"],
            capture_output=True, text=True, timeout=30,
        )
        return {
            "restarted": True,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except FileNotFoundError:
        # Try common install locations as fallback
        common_paths = [
            "/usr/local/bin/openclaw",
            os.path.expanduser("~/.npm-global/bin/openclaw"),
            os.path.expanduser("~/.local/bin/openclaw"),
        ]
        openclaw_path = next((p for p in common_paths if os.path.exists(p)), None)
        if openclaw_path:
            result = subprocess.run(
                [openclaw_path, "gateway", "restart"],
                capture_output=True, text=True, timeout=30,
            )
            return {
                "restarted": True,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        logger.warning("openclaw binary not found")
        return {"restarted": False, "error": "openclaw binary not found"}
    except subprocess.TimeoutExpired:
        return {"restarted": False, "error": "Gateway restart timed out"}
