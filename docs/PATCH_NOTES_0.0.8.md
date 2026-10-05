# Jarvis Core v2 0.0.8 — Client Input & Runtime Control

## Summary

0.0.8 completes the first two-way local Runtime API boundary. Clients can now submit typed user input into the existing authoritative Conversation Core, receive server-owned correlation IDs, retry ambiguous submissions without duplicate execution, observe results through the existing event stream, and cancel an active client command through Core's cooperative cancellation path.

This milestone does not add a second conversation engine, client-owned runtime state, remote network exposure, a desktop/mobile UI, tools, permissions, memory, or autonomous tasks.

## V1 reference review before implementation

The read-only V1 0.3.6 checkpoint was reviewed before implementation.

Applied lessons:

- **ISSUE-075 — duplicate transports need idempotency, not semantic collapse.** `client_request_id` protects transport retries while genuine later repeated user text remains a new turn.
- **ISSUE-117 / ISSUE-205 — one response owner.** Duplicate/retried client submissions reuse one in-flight/completed command record instead of starting competing provider work.
- **ISSUE-172 — cancellation is separate control.** Cancel goes through an explicit endpoint/Core cancellation path and is never interpreted as another user/confirmation turn.
- **ISSUE-310 — clients are not authority.** Runtime/Core generate trace IDs and own execution state; client platform/IDs are correlation metadata only.
- Existing 0.0.7 reconnect lessons remain enforced: clients target a specific runtime/conversation and consume authoritative events/snapshots rather than reconstructing state locally.

## Added

### RuntimeCommandGateway

`core/runtime/commands.py` adds a bounded in-memory client request gateway owned by `JarvisRuntime`.

For each accepted typed command the runtime generates:

- `command_id`
- `correlation_id`
- `request_id`
- `turn_id`
- `cancellation_id`

The client supplies none of those Jarvis trace IDs.

### Retry-safe typed submission

`POST /v1/runtime/commands/typed` requires:

- current `runtime_id`;
- current `conversation_id`;
- a client-generated `client_request_id` for transport retry identity;
- informational `client_id`;
- typed user text.

The server responds with a `client.command.ack` envelope. Retrying the same `client_request_id` + same payload returns the same command and trace with `duplicate=true`. Reusing the same request ID for different input is rejected as `idempotency-conflict`.

A stale runtime/conversation is rejected before execution. A second client command while the foreground Core is busy is rejected instead of being invisibly queued.

### Client cancellation

`POST /v1/runtime/commands/{command_id}/cancel` delegates to the same Conversation Core cancellation registry/provider cancellation path already used by the runtime. The client cannot set Core state directly or cancel an unrelated arbitrary turn through this command-specific endpoint.

### Authoritative command events

Command lifecycle is emitted on the existing EventBus:

- `runtime.client.command.accepted`
- `runtime.client.command.started`
- `runtime.client.command.completed`
- `runtime.client.command.cancel.requested`
- `runtime.client.command.cancelled`
- `runtime.client.command.failed`

The existing Runtime API WebSocket/replay contract delivers these events with the same server-owned trace IDs returned in the HTTP acknowledgement.

### Runtime API Lab expansion

`python -m apps.runtime_api_lab` now proves over real loopback TCP/HTTP/WebSocket:

1. typed command acceptance;
2. trace correlation between HTTP ACK and event stream;
3. duplicate-retry suppression (provider executes once);
4. command completion while the observing client is disconnected;
5. replay after reconnect;
6. active command cancellation through Conversation Core;
7. preservation of the same authoritative Conversation Core instance.

No microphone, local TTS, Luna credential, or public Internet is required.

## Protocol / security boundary

Protocol version remains `jarvis-runtime` v1 because 0.0.8 is additive and does not break the existing snapshot/event contract.

The API remains loopback-only. `client_id`, platform metadata, and `client_request_id` are never authentication/permission authority. Authenticated device pairing, TLS/relay transport, account authority, and remote exposure remain deferred.

## Voice impact

The accepted voice path is intentionally unchanged. The only Conversation Core change is an internal optional server-owned trace hook for trusted in-process adapters; ordinary typed/voice callers still receive Core-generated traces exactly as before.

## Deferred

- durable command queue / idempotency across Core process restart;
- generic client queueing policy or arbitrary runtime-state mutation RPCs;
- LAN/WAN exposure, device pairing, TLS/cloud relay;
- production desktop/mobile client;
- tools/permissions;
- Memory 2.0;
- autonomous tasks;
- fuzzy wake-word correction.
