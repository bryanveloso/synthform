# Synthform

> Personal streaming-overlay frontend (React/Vite) — single-tenant (avalonstar). Consumes synthfunc over WebSocket and the other backends over REST; renders OBS overlays.

## Overview

Synthform is a personal streaming overlay frontend built with React, Vite, and TailwindCSS. It is a single-tenant app (always `avalonstar`) designed for a local Tailscale network. It provides real-time, animated overlays for OBS streaming, including timer displays, Pokémon game trackers, and customizable visual elements. It consumes real-time data over WebSocket from Synthfunc and historical data over HTTP from Questlog.

## Conventions

@~/Code/standards/conventions/typescript.md

Project-specific deltas (everything else is inherited from the import above and ~/.claude/CLAUDE.md):

- **Commits:** open to agents, like the rest of the rack (the Dev-only rule was retired 2026-08-28). Stage paths, never `git add -A`.
- Single-tenant (always `avalonstar`); runs on the Tailscale LAN.
- **Ports, Redis DB, container names:** not restated here. `recall("<project> port")` or `lookup` against `registry/allocations.md`, which is canonical and derived from what is actually listening. A copy in this file is a second place to be wrong.
- **No mock mode** — real data/APIs only.
- **Don't reimplement from scratch** without explicit permission; make the smallest reasonable change; never rename things "improved"/"new"/"enhanced".
- **Ask for clarification** rather than assuming; it's fine to stop and ask for help.
- Uses Zustand for client state and the `generate:api` OpenAPI codegen pipeline (both the suite TS standard).
- **Comments:** never remove one unless it's provably false; keep comments evergreen — describe the code as it is, not how it changed.
- Update `CHANGELOG.md` as the final step if one exists.
