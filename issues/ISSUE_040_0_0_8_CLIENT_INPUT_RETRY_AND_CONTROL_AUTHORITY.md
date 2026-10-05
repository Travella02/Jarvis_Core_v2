# ISSUE 040 — 0.0.8 client input needed retry-safe Core authority

## Symptom / architectural gap

0.0.7 let a UI observe and reconnect to one authoritative `JarvisRuntime`, but typed commands still had to be injected in-process. A real client could not safely submit a user turn, retry after an ambiguous network response, or cancel its own active request without either inventing a second conversation path or risking duplicate execution.

## V1 lessons reviewed

V1 repeatedly showed that duplicate transport/provider events can create duplicate responses/actions when more than one layer believes it owns the turn. V1 also showed that cancellation must be separate from positive execution/confirmation and that a modified client cannot be trusted as server/Core authority.

## 0.0.8 resolution

- Add a runtime-side `RuntimeCommandGateway` over the existing `ConversationCore`.
- Require current `runtime_id` and `conversation_id` on every client command.
- Generate Jarvis correlation/request/turn/cancellation IDs inside Core/runtime; clients cannot provide them.
- Bind one runtime-scoped `client_request_id` to one typed-command payload.
- Return the same command/trace on duplicate retry and reject request-ID rebinding to different input.
- Reject a second client command while another foreground turn is active instead of creating a hidden queue.
- Route client cancellation through `ConversationCore.cancel_active_turn` and its existing cancellation registry/provider hook.
- Emit command lifecycle events into the existing authoritative EventBus so reconnect replay can recover accepted/completed/cancelled state.

## Deferred

Durable command queues/idempotency across Core restart, authenticated remote transport, device pairing, account authority, production UI, tools/permissions, and Memory 2.0 remain later milestones.
