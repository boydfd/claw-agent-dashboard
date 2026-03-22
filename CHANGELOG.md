# Changelog

## v0.3.0 (2026-03-22)

### Features
- **Mobile responsive layout** — Full responsive CSS for dashboard, agent management, blueprints, sessions, and file views. Two-step mobile navigation for diffs, overflow dropdown for toolbar buttons, touch-friendly session cards
- **Session compose** — Send messages directly from the session detail page with a compose bar, view mode toggle (Chat/Detail), and send mode toggle (Envelope/Raw)
- **Chat view mode** — Simplified message display showing only user inputs and agent replies, filtering out tool calls and thinking blocks
- **Envelope formatting** — Wrap outgoing messages with OpenClaw-compatible context headers (channel, sender, timestamps, elapsed time)
- **Responsive composable** — `useResponsive()` composable for consistent breakpoint handling across components

### Fixes
- Fix empty message bubbles in chat view mode — strip directive tags and filter empty blocks
- Fix mobile session interactions (switch-model, new-session buttons, scroll behavior)

### Internal
- Add `test_session_compose.py` with envelope formatting and elapsed time tests (17 new tests, 113 total)
- Add mobile regression test scripts with Playwright

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
