# Jarvis Core v2 0.0.4 Repair36 — GPT-6 Luna Control + WebSocket Continuation Fix

Repair35 showed that Fast mode's latency gain was not worth making its 2x token price the Jarvis default, and it also exposed that Conversation Core reported `continuation=no` on every round even though the WebSocket connection itself was reused.

## Continuation root cause

The provider persisted `_VoiceLaneState` only after yielding the terminal `COMPLETED` event. Conversation Core intentionally stops consuming the provider stream as soon as it receives `COMPLETED`, so the async generator could close at that yield before the lane-persistence lines ever executed.

Repair36 commits or clears lane state before yielding the terminal event.

Expected:
- turn 1: `continuation=no reason=no_lane lane_committed=yes`
- turn 2+: `continuation=yes reason=exact_chain lane_committed=yes`

When continuation is valid, only the new user message is sent together with `previous_response_id` and the same `stream_id`.

## Model control

- Candidate/default model: `gpt-6-luna`
- Voice reasoning remains `none`
- Standard service tier default: `default`
- Fast mode remains explicit opt-in
- Environment pin: `JARVIS_OPENAI_MODEL=<exact-model-id>`
- Voice Lab override: `--luna-model <exact-model-id>`
- Probe override: `--model <exact-model-id>`

There is intentionally no blind automatic "latest" upgrade. ORVEX controls the approved exact model ID so a future Luna model can be benchmarked before promotion.

## Unchanged

Jarvis personality, humor, response freedom, whole-response Qwen synthesis, fixed Qwen seed, Whisper, permissions, and tool authority are untouched.
