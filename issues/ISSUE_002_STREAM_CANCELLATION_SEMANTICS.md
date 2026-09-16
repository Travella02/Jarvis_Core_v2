# ISSUE_002 — Streaming cancellation semantics

## Version / candidate

0.0.2 - Intelligence Provider

## Symptom

Jarvis needs fast interruption/cancellation, but a normal foreground Responses API SSE stream does not expose the same server-side cancel operation as a background response. Closing the client stream stops Jarvis from consuming more output, but 0.0.2 must not overstate that as a guaranteed server-side inference cancellation.

## Reproduction

Start a foreground streamed provider request and invoke `IntelligenceProvider.cancel(request_id)` while deltas are arriving.

## Expected behavior

The provider must stop delivering deltas promptly, close its active stream, emit a provider-neutral `CANCELLED` terminal event, and release active-request state. Later realtime milestones must separately verify whether the chosen transport provides sufficiently strong server-side cancellation for barge-in latency and cost control.

## Root cause

OpenAI's Responses cancellation endpoint is documented for responses created with `background=true`, while 0.0.2 intentionally uses foreground streaming for the smallest launch intelligence path.

## Investigation

The current OpenAI Python SDK and API reference were checked before implementation. The foreground stream itself is closeable; the separate `responses.cancel(response_id)` operation is documented as background-response cancellation.

## Attempted fixes

Using background mode solely to gain the cancel endpoint was rejected because it would change the foreground streaming lifecycle and add complexity before the conversation/voice milestones establish their transport requirements.

## Final fix

0.0.2 defines cancellation honestly as cooperative provider-stream cancellation: cancellation is monotonic, the active stream is closed, no further provider deltas are exposed to Core, a `CANCELLED` event is emitted, and the request is removed from the active registry. No server-side cancellation guarantee is claimed in this milestone.

## Regression tests

- `test_pre_cancelled_request_never_creates_provider_stream`
- `test_cancel_closes_active_stream_and_emits_cancelled`

## Verification / live outcome

Automated fake-stream tests pass. Transport-level interruption behavior against a live model remains part of live acceptance and must be revisited before the realtime voice/barge-in milestone.

## Regression risk

If later code assumes `cancel()` proves remote inference termination, costs or stale server work could continue after Jarvis has locally moved on.

## Technical lesson

Keep the Core cancellation contract provider-neutral, but document transport semantics precisely. Barge-in requires measured end-to-end cancellation behavior, not merely a method named `cancel`.
