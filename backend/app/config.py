import os

# Directory where agent workspaces are mounted (read-only)
AGENTS_DIR = os.environ.get("AGENTS_DIR", "/agents")

# Blueprint filesystem directory (under AGENTS_DIR)
BLUEPRINTS_DIR = os.path.join(AGENTS_DIR, "blueprints")

# Directory for writable data (translations, config)
DATA_DIR = os.environ.get("DATA_DIR", "/data")

# Host path mappings (for displaying real paths to users)
AGENTS_HOST_DIR = os.environ.get("AGENTS_HOST_DIR", "")
DATA_HOST_DIR = os.environ.get("DATA_HOST_DIR", "")

# Global skills directories
GLOBAL_SKILLS_DIR = os.environ.get("GLOBAL_SKILLS_DIR", "/global-skills")
SHARED_SKILLS_DIR = os.environ.get(
    "SHARED_SKILLS_DIR", os.path.join(AGENTS_DIR, "shared-skills")
)

# Gateway logs directory (mounted from host /tmp/openclaw)
LOGS_DIR = os.environ.get("LOGS_DIR", "/host/logs")

# Session data directory (mounted from host ~/.openclaw/agents)
SESSION_DATA_DIR = os.environ.get("SESSION_DATA_DIR", "/host/openclaw-data/agents")

# OpenClaw configuration file path (JSON with comments)
OPENCLAW_CONFIG_PATH = os.environ.get("OPENCLAW_CONFIG_PATH", "/agents/openclaw.json")

# Gateway URL for creating new sessions
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://host.docker.internal:18789")

# Gateway authentication token
GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "")
