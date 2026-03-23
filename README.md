[中文](README_CN.md)

# Claw Agent Dashboard

A web-based management dashboard for [OpenClaw](https://github.com/openclaw/openclaw) AI agents. Monitor system health, browse agent workspaces, manage sessions, edit blueprints, and interact with your agents — all from a single UI.

<!-- ![Screenshot](docs/screenshot.png) -->

## What Is This?

[OpenClaw](https://github.com/openclaw/openclaw) is a platform for running AI agents across multiple messaging channels (Signal, Telegram, Nextcloud Talk, etc.). Each agent has a **workspace** — a set of configuration files (personality, tools, memory, skills) that define its behavior.

**Claw Agent Dashboard** gives you a centralized web interface to:

- **See what your agents are doing** — live session history, message streams, model usage
- **Edit how they behave** — modify blueprints, sync changes to workspaces, review diffs before applying
- **Monitor your system** — CPU, memory, disk, Gateway health, all in real time
- **Search across everything** — full-text search through files and session transcripts
- **Talk to your agents** — send messages directly from the session detail page

It's designed for OpenClaw operators who want visibility and control without SSH-ing into their server.

## Key Features

### 🤖 Agent Management
- **Workspace File Browser** — Browse all agent workspace files (`SOUL.md`, `AGENTS.md`, `TOOLS.md`, skills, memory, etc.) with syntax highlighting and in-browser editing
- **Blueprint Editor** — View, compare, and sync blueprint-to-workspace changes with inline diff review. Blueprints are templates; workspaces are live — the dashboard shows you exactly what's different
- **Global Skills Browser** — Explore globally installed OpenClaw skills and their configurations

### 💬 Session Monitoring & Interaction
- **Session Viewer** — Paginated message history for every agent session, showing provider, model, timestamps, tool calls, and thinking blocks
- **Session Compose** — Send messages directly from the session detail page. Choose between:
  - **Raw mode** — send plain text directly to the agent
  - **Envelope mode** — wrap messages with OpenClaw-compatible context headers (channel, sender, timestamps) to simulate channel input
- **Chat View Mode** — Toggle between detailed view (full verbose output including tool calls) and chat view (clean conversation showing only user messages and agent replies)
- **Model Switching** — Switch the active model for any running session

### 🔍 Search
- **File Search** — Full-text search across all agent workspace files with jump-to-result and keyword highlighting
- **Session Search** — Search across agent session transcripts (requires Elasticsearch) with hit highlighting

### 📊 System Monitoring
- **Dashboard** — Real-time system metrics: CPU, memory, disk, and network usage
- **Gateway Health** — Monitor OpenClaw Gateway status, connectivity, and uptime
- **Change Detector** — Background file watcher that detects workspace changes and notifies you

### 📝 Other
- **File Translation** — Translate any workspace file to Chinese using a configurable LLM service (OpenAI-compatible API)
- **File Version History** — Track file changes over time with inline diff comparison and one-click restore to previous versions
- **Mobile Responsive** — Full responsive layout for phones and tablets — manage your agents on the go
- **Bilingual UI** — Complete English and Chinese interface

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- A running [OpenClaw](https://github.com/openclaw/openclaw) instance

### Option A — Docker Hub (recommended)

```bash
# 1. Create a project directory
mkdir claw-agent-dashboard && cd claw-agent-dashboard

# 2. Download config files
curl -LO https://raw.githubusercontent.com/boydfd/claw-agent-dashboard/main/docker-compose.yml
curl -LO https://raw.githubusercontent.com/boydfd/claw-agent-dashboard/main/.env.example
cp .env.example .env

# 3. Edit .env — at minimum set OPENCLAW_HOME and GATEWAY_TOKEN
#    (see Configuration below)

# 4. Start
docker compose up -d
```

### Option B — Build from source

```bash
git clone https://github.com/boydfd/claw-agent-dashboard.git
cd claw-agent-dashboard
cp .env.example .env
# Edit .env
docker compose up -d --build
```

Then open [http://localhost:8080](http://localhost:8080).

## Configuration

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `OPENCLAW_HOME` | Yes | Path to your OpenClaw home directory (`~/.openclaw`) | `~/.openclaw` |
| `DATA_HOST_DIR` | Yes | Writable data directory for translations, version DB, config | `./data` |
| `GATEWAY_URL` | No | OpenClaw Gateway URL | `http://host.docker.internal:18789` |
| `GATEWAY_TOKEN` | Yes | Gateway authentication token (see below) | — |
| `ALLOWED_ORIGINS` | No | CORS allowed origins (comma-separated) | `*` |
| `OPENCLAW_SKILLS_DIR` | No | Path to global skills directory | — |
| `OPENCLAW_LOGS_DIR` | No | Path to OpenClaw logs directory | — |
| `OPENCLAW_AGENTS_DIR` | No | Custom agents directory (overrides `OPENCLAW_HOME/agents`) | — |

### Getting `GATEWAY_TOKEN`

The dashboard authenticates with the OpenClaw Gateway to read sessions, switch models, and send messages. Find your token in OpenClaw's config:

```bash
cat ~/.openclaw/openclaw.json | python3 -c "import sys,json; print(json.load(sys.stdin)['gateway']['auth']['token'])"
```

Or look for `gateway.auth.token` in `~/.openclaw/openclaw.json`:

```jsonc
{
  "gateway": {
    "auth": {
      "mode": "token",
      "token": "your-token-here"   // ← copy this
    }
  }
}
```

> **Note:** If `gateway.auth.mode` is not `"token"`, the Gateway may not require authentication — you can leave `GATEWAY_TOKEN` empty.

### Build Args (for proxy / mirror environments)

| Build Arg | Description | Default |
|-----------|-------------|---------|
| `NPM_REGISTRY` | npm registry mirror | `https://registry.npmjs.org` |
| `PIP_INDEX_URL` | pip index URL | `https://pypi.org/simple` |

```bash
docker compose build \
  --build-arg NPM_REGISTRY=https://registry.npmmirror.com \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

## Architecture

```
┌─────────────────────────────────────────────┐
│              Docker Container               │
│                                             │
│  ┌─────────────┐   ┌────────────────────┐  │
│  │  Vue 3 SPA  │──▶│  FastAPI (:8080)   │  │
│  │  (static)   │   │                    │  │
│  └─────────────┘   │  REST APIs:        │  │
│                     │  • /api/agents     │  │
│                     │  • /api/status     │  │
│                     │  • /api/translate  │  │
│                     │  • /api/versions   │  │
│                     │  • /api/search     │  │
│                     │  • /api/blueprints │  │
│                     │  • /api/settings   │  │
│                     └───┬────────┬───────┘  │
│                         │        │          │
│                  ┌──────▼──┐ ┌───▼────┐     │
│                  │ /agents │ │ /data  │     │
│                  │ (r/w)   │ │ (r/w)  │     │
│                  └─────────┘ └────────┘     │
└─────────────────────────────────────────────┘
         │                          │
    ~/.openclaw               ./data
   (agent workspaces,       (versions.db,
    blueprints, config)      translations)
```

- **Frontend**: Vue 3 + Element Plus + Pinia, built with Vite, served as static files
- **Backend**: FastAPI (Python) providing REST APIs, proxying to the OpenClaw Gateway for session and agent data
- **Storage**: Bind-mounted host directories — `/agents` for OpenClaw home, `/data` for dashboard-specific data (SQLite version DB, translations, config)
- **Process Manager**: supervisord runs the FastAPI server and a background worker (change detection, file version tracking)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vue 3, Element Plus, Pinia, Vite, markdown-it, highlight.js, Monaco Editor |
| Backend | Python 3.12, FastAPI, httpx, aiosqlite |
| Infrastructure | Docker, supervisord |
| Testing | pytest (backend), Playwright (E2E) |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).

Copyright 2026 Lin Ran.
