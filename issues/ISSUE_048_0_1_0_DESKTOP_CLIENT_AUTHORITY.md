# ISSUE-048 — Desktop UI must not become a second Jarvis authority

**Milestone:** 0.1.0 Desktop App Alpha  
**Status:** Prevented by architecture/tests

## Risk

Moving the successful Realtime WebRTC harness into a native desktop app could accidentally reintroduce V1-style coupling: UI-owned state, duplicate Core startup, API keys in the renderer, or separate typed/voice conversation paths.

## 0.1.0 rule

Electron owns native lifecycle. React owns presentation plus browser-grade WebRTC media. Python Jarvis Core owns runtime/conversation authority, Core delegation, durable product state, and provider/backend routing.

Typed input is inserted into the same Realtime session as speech. It is not routed through a second UI-specific intelligence system.

The renderer never receives `OPENAI_API_KEY`.

## V1 lessons applied

- Browser tab cannot own desktop lifecycle (`ISSUE-020`).
- Electron/Core process ownership must not double-start the fixed loopback service (`ISSUE-312`).
- WebRTC belongs in the client interaction layer while Python Core remains independent.

## Regression protection

0.1.0 tests inspect the Electron security/process contract, desktop-host loopback/runtime contract, renderer Realtime typed-input contract, and progressive transcript/avatar-state behavior.
