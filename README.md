[中文](README_CN.md)

# claw-agent-dashboard

A web dashboard for monitoring and managing [OpenClaw](https://github.com/openclaw/openclaw) AI agents.

<!-- ![Screenshot](docs/screenshot.png) -->

## Features

- **Agent Workspace File Browser** — Browse agent workspace files with syntax highlighting and in-browser editing
- **Session Viewer** — View agent session history with paginated message display
- **File Translation** — Translate any file to Chinese using a built-in LLM-powered translation service
- **File Version History** — Compare file versions with diff view and one-click restore
- **System Metrics Dashboard** — Monitor CPU, memory, disk, and network usage in real time
- **Gateway Health Monitoring** — Track OpenClaw Gateway status and connectivity
- **Global Skills Browser** — Explore globally installed OpenClaw skills
- **Bilingual UI** — Full English and Chinese interface support

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/openclaw/claw-agent-dashboard.git
cd claw-agent-dashboard

# 2. Copy and edit the environment file
cp .env.example .env
# Edit .env with your settings (see Configuration below)

# 3. Start the service
docker compose up -d
```

Access the dashboard at [http://localhost:8080](http://localhost:8080).

## Configuration

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `OPENCLAW_HOME` | Yes | Path to OpenClaw home directory | `~/.openclaw` |
| `DATA_HOST_DIR` | Yes | Path to writable data directory (translations, config) | `./data` |
| `GATEWAY_URL` | No | OpenClaw Gateway URL | `http://host.docker.internal:18789` |
| `GATEWAY_TOKEN` | Yes | Gateway authentication token | — |
| `OPENCLAW_SKILLS_DIR` | No | Custom global skills directory | — |
| `OPENCLAW_LOGS_DIR` | No | Custom logs directory | — |
| `OPENCLAW_AGENTS_DIR` | No | Custom agents directory | — |

## Build Args

If you are behind a proxy or need to use registry mirrors, pass build args:

| Build Arg | Description | Default |
|-----------|-------------|---------|
| `NPM_REGISTRY` | npm registry mirror | `https://registry.npmjs.org` |
| `PIP_INDEX_URL` | pip index URL | `https://pypi.org/simple` |

Example:

```bash
docker compose build \
  --build-arg NPM_REGISTRY=https://registry.npmmirror.com \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

## Architecture

The frontend is a Vue 3 single-page application served by the FastAPI backend. The backend exposes REST APIs for file browsing, translation, version history, and system metrics, and acts as a proxy to the OpenClaw Gateway API for agent and session data.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).

Copyright 2026 Lin Ran.
