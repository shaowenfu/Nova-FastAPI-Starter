# Nova FastAPI Starter · Progress Log

Purpose: track important/structural updates. Keep entries concise, deterministic, and reviewable.

## Update Rules
- Scope: architecture/layout changes, config/env schema updates, dependency shifts, breaking API/WS contract changes, infra/docker adjustments, and key docs revisions.
- Format: append as table rows with date (YYYY-MM-DD), area, change summary, author/PR (if applicable).
- Exclusions: routine refactors without behavior change, minor copy tweaks, formatting-only commits.
- When to update: whenever a change impacts how to run, configure, extend, or integrate the framework.

## Log
| Date       | Area            | Change                                                                 | Author/PR |
| ---------- | --------------- | ---------------------------------------------------------------------- | --------- |
| 2024-06-XX | Docker/Config   | Simplified Dockerfile/compose; unified `.env.example`; ops profiles.   | -         |
| 2024-06-XX | WS/Services     | Consolidated WebSocket manager/service; pruned domain handlers.        | -         |
| 2024-06-XX | Docs/Static     | Rebuilt static index/auth guide/WS tester/notifications as generic.    | -         |
| 2025-12-14 | Architecture    | Renamed to "Nova"; decoupled Config (LLM/SMS); added Docker Memory Adapter (Chroma). | -         |