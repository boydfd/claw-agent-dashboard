# Changelog

## v0.2.0 (2026-03-21)

### Features
- **Provider/Model display** — Show provider and model info in session list and message headers
- **Version history redesign** — New `VersionHistoryPanel` and `VersionDiffView` components replace the old `VersionDrawer`, with cleaner inline diff rendering
- **Client-side diff utility** — `frontend/src/utils/diff.js` for unified diff parsing and display
- **Async workers** — Background tasks separated into `backend/app/worker.py` using supervisord for multi-process deployment
- **Blueprint management improvements** — Streamlined `BlueprintsPanel` with simplified diff review flow

### Fixes
- Fix model switch regression — restore native session model override switching
- Fix version diff route unreachable due to greedy path parameter ordering
- Fix change detector to scan all managed subdirectories
- Fix async wrappers for scanner and file_service to prevent event loop blocking

### Internal
- Add `test_change_detector_guards.py` test coverage
- Add async service wrappers for scanner and file_service
- Dockerfile: switch to official Miniconda URL, increase Playwright timeout

## v0.1.0 (2026-03-19)

### Features
- **Blueprint management** — View, compare, and sync blueprint-to-workspace changes
- **Full-text search** — File content search with jump-to-result and highlight
- **Elasticsearch session search** — Search across agent session transcripts (when ES is configured)
- **Change detector** — Background disk sync that detects workspace file changes
- **Security hardening** — Removed hardcoded credentials and internal paths

### Fixes
- Fix session indexer message_index alignment with API offset
- Fix session indexer aiosqlite compatibility + OpenClaw transcript format parsing
- Fix search highlight rendering bugs
- Fix main agent not showing in dashboard

## v0.0.1 (2026-03-16)

Initial open-source release.

### Features
- Agent workspace file browser with syntax highlighting
- Session viewer with paginated message history
- Built-in LLM-powered file translation
- File version history with diff comparison and restore
- System metrics dashboard (CPU, memory, disk, network)
- OpenClaw Gateway health monitoring
- Global skills browser
- Bilingual UI (English / Chinese)
