# Jarvis Core v2 0.0.7 — Portable Runtime API & Client Reconnection

## Summary

0.0.7 turns the in-process 0.0.6 reconnect contract into a real local HTTP/WebSocket boundary without making the client a second Jarvis authority.

The protocol is deliberately platform-neutral. Windows, macOS, Linux, iOS, and Android clients can consume the same versioned JSON contract. No Electron IPC, Windows named pipes, Python object pickling, or provider-specific transport state appears in the public client protocol.

This milestone does **not** yet expose Jarvis over the LAN or Internet. The local API binds to loopback only. Cross-device networking requires an authenticated/TLS transport or relay and is intentionally deferred rather than shipping an unauthenticated LAN control surface.

## V1 reference review before implementation

The read-only V1 0.3.6 checkpoint was reviewed before implementation, especially the server/client lifecycle and repair history.

Applied lessons:

- **One Core owner.** V1 Issue 312 showed that a desktop shell and a manually started server could both believe they owned Core, causing port conflicts and restart loops. `create_app(runtime)` receives an already-owned `JarvisRuntime`; it does not create another Core or Conversation Core.
- **Reconnect must be automatic and identity-aware.** V1 Issue 280 showed that in-memory reconnect timers are not a sufficient recovery contract. V2 clients reconnect from a `runtime_id + event cursor`, not from UI state.
- **A healthy HTTP endpoint is not proof that WebSockets work.** V1 Issue 300 exposed missing WebSocket runtime dependencies only after a client connected. 0.0.7 makes FastAPI/Uvicorn/WebSockets direct pinned dependencies and adds real WebSocket integration tests plus a real TCP Runtime API Lab.
- **Validate at the API boundary.** V1 Issue 007 showed provider-dependent validation bugs. Replay limits, protocol versions, cursor values, and local exposure policy are validated before client state is accepted.
- **Tests must not inherit private developer config.** V1 Issue 033 remains enforced: Runtime API settings are deterministic unless an env file is explicitly supplied.
- **Runtime identity matters after restart.** V1 cross-device/cloud-sync work demonstrated that client clocks and local assumptions are not authority. 0.0.7 treats a cursor as valid only with the matching `runtime_id`; a new runtime forces snapshot reset instead of falsely resuming old history.

The V1 project remains read-only and is not imported by v2.

## Added

### Versioned portable protocol

`core/runtime/protocol.py` defines `jarvis-runtime` protocol version 1 and deterministic JSON serialization for:

- runtime snapshots;
- health projection;
- Core events and trace IDs;
- event batches;
- protocol capability metadata.

Opaque binary/native objects are rejected rather than stringified into the client API.

### Race-safe reconnect stream

`RuntimeEventStream` subscribes to the EventBus **before** capturing the reconnect snapshot. That prevents the classic snapshot/replay race where an event can happen between “read state” and “start listening.”

Reconnect outcomes are explicit:

- `resume_accepted=true` — replay can continue from the supplied cursor;
- `runtime-identity-required` — a nonzero cursor was supplied without its runtime identity;
- `runtime-changed` — Core restarted and the old cursor is not authoritative;
- `cursor-ahead` — client cursor is impossible for this runtime;
- `history-gap` — bounded in-memory replay no longer contains all missed events;
- `replay-limit` — missed history is too large for one safe reconnect payload.

A slow client queue never silently drops authoritative events. Overflow produces a resync requirement.

### Local HTTP/WebSocket API

`apps/runtime_api.py` exposes:

- `GET /v1/protocol`
- `GET /v1/health`
- `GET /v1/runtime/snapshot`
- `GET /v1/runtime/events`
- `WS /v1/runtime/events/ws`

The WebSocket handshake sends:

1. `hello`
2. `sync` — authoritative snapshot plus optional missed-event replay
3. `ready`
4. live `event` messages

The client platform string is informational only. Claiming `ios`, `android`, or any other platform never changes permissions or server authority.

### Real network diagnostic

`python -m apps.runtime_api_lab` starts a real loopback Uvicorn server on an ephemeral port, connects over HTTP and WebSocket, disconnects the client, advances Conversation Core while the client is absent, reconnects from the old cursor, and verifies:

- same runtime identity;
- same Conversation Core identity;
- missed turn replay;
- no client-owned state reconstruction;
- platform-neutral client contract.

No provider credential, microphone, TTS model, or external network is used.

## Security / cross-device boundary

0.0.7 deliberately permits only loopback API hosts (`127.0.0.1`, `::1`, or `localhost`). `0.0.0.0`, LAN addresses, and WAN exposure are rejected by `RuntimeSettings`.

This is not a desktop-only architecture. It separates **protocol portability** from **network trust**:

- a Windows/macOS/Linux desktop app can connect locally;
- a future iOS/Android app can use the same JSON protocol through an on-device host or authenticated remote transport;
- a future secure relay can carry the same protocol without teaching Core about Electron or a particular mobile framework.

Authentication, device pairing, TLS/relay transport, account authority, and cross-device state sync are separate milestones and must land before remote exposure is enabled.

## Deferred

- production desktop/mobile UI;
- LAN/WAN exposure;
- authenticated device pairing;
- cloud relay / account-backed remote connection;
- durable event replay across Core process restart;
- typed command submission through the API;
- tools, memory, and autonomous jobs;
- fuzzy wake-word correction (`Jervis` -> `Jarvis`).
