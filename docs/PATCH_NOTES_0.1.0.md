# 0.1.0 — Desktop App Alpha

## Goal

Move the accepted 0.0.9 Realtime Mini + Cedar + WebRTC conversational experience out of the browser lab and into the first real Jarvis desktop shell without moving authority out of Jarvis Core.

## V1 lessons reviewed before implementation

The V1 desktop reference established several rules that 0.1.0 keeps:

- Electron owns native desktop lifecycle; the renderer must not own/reconstruct Core.
- exactly one process owns Core startup; startup must preflight the fixed loopback port rather than double-starting Core,
- client media belongs in the interaction layer through WebRTC,
- renderer security defaults remain `contextIsolation=true`, `nodeIntegration=false`, and sandboxed,
- the application API key stays in the trusted Python/Core side rather than the renderer,
- browser/UI closure and Core shutdown must tear down the active realtime session.

## Added

- `apps.desktop_alpha`: loopback FastAPI host for the first desktop client.
- Electron native shell with single-instance protection, Core supervision, loopback-only navigation, media permission scoping, and graceful Core/session teardown.
- React/TypeScript renderer built by Vite.
- code-native abstract Jarvis avatar with visual states: connecting, idle, listening, thinking, speaking, working, error.
- progressive Jarvis speech transcript from Realtime audio transcript deltas.
- typed input into the **same Realtime conversation** using `conversation.item.create` + `response.create`.
- the existing versioned Runtime API mounted under `/runtime` for future app growth instead of duplicating Core logic.

## Intentionally deferred

- chat history/sidebar and multiple chat selection,
- accounts/settings UI,
- wake/sleep product lifecycle,
- task/memory/tool/permission surfaces,
- avatar final art/3D identity,
- installer/package distribution,
- cloud/remote Core,
- production auto-update/tray behavior.

## Authority invariant

Electron/React is a client. It may render state, carry WebRTC media, and submit user input. Jarvis Core remains authoritative for memory, permissions, tools, tasks, durable state, delegated work, and backend model routing.
