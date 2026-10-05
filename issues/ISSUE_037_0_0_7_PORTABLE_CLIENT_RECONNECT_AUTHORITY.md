# ISSUE 037 — Portable clients need reconnect authority without becoming Core authority

## Problem

0.0.6 established snapshots and event cursors in-process, but a real UI/mobile client boundary did not yet exist. A naive network adapter could reintroduce V1 problems: a second Core owner, stale UI state after Core restart, missed events during snapshot/subscription races, silent queue drops, platform-specific IPC coupling, or unauthenticated LAN exposure.

## V1 lessons reviewed

- ISSUE-312: two launch paths could both try to own Core and collide on the fixed port.
- ISSUE-280: reconnect logic tied to one in-memory client worker was not durable enough after runtime restart.
- ISSUE-300: HTTP health could work while WebSocket support was missing from the actual runtime environment.
- ISSUE-007: provider-independent validation belonged at the API boundary.
- ISSUE-033: server tests could accidentally inherit private `.env` values.
- ISSUE-307: cross-device authority cannot be based on client clocks or client-supplied identity claims.

## 0.0.7 resolution

- Version one platform-neutral JSON protocol over HTTP/WebSocket.
- Keep `JarvisRuntime` and Conversation Core server-owned.
- Reconnect with the pair `runtime_id + event sequence`.
- Subscribe before snapshot capture so reconnect has no event race.
- Force snapshot reset when runtime identity changes, replay history is stale, or replay is too large.
- Detect slow-client backpressure rather than silently dropping events.
- Pin WebSocket/server dependencies directly and test a real TCP/WebSocket path.
- Permit loopback binding only until authenticated remote transport/device pairing exists.

## Cross-platform consequence

The protocol is usable by native Windows, macOS, Linux, iOS, and Android clients. Network exposure policy remains separate from client platform. Remote/mobile transport can later wrap the same protocol in authenticated TLS/relay infrastructure without rewriting Jarvis Core around a specific UI framework.
