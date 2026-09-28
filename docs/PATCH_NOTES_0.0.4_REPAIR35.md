# Jarvis Core v2 0.0.4 Repair35 — Luna Path Verification + Fast A/B

Repair34a/b is the committed low-latency STT + whole-response voice baseline.

Luna is now the largest variable stage, commonly around 0.55-0.65 s to first
text in recent Voice Lab runs. Repair35 does not make Jarvis shorter, flatter,
or less human. It instruments the exact OpenAI path and exposes Fast mode as
an opt-in A/B.

## Per-turn Luna path telemetry

Voice Lab now prints:
- transport;
- whether `previous_response_id` continuation was actually used;
- whether the WebSocket connection was reused;
- number of input items sent;
- requested service tier;
- actual service tier returned by OpenAI;
- SDK `response.create` return time;
- provider-side time to first text.

Healthy WebSocket behavior:
- turn 1: continuation=no, full input;
- turn 2+: continuation=yes, input_items=1, connection_reused=yes.

## Fast-mode A/B

Voice Lab adds:
`--luna-service-tier fast`

Omitting it preserves the committed configuration. `priority` is also accepted
because OpenAI treats `priority` and `fast` as the same Fast-mode request on
supported GPT-5.6 models.

## Luna-only probe

`apps.luna_latency_probe` now accepts explicit:
- `--transport websocket|http`
- `--service-tier auto|default|fast|priority`

This measures Luna without Whisper, Qwen, PortAudio, or microphone variance.

## Unchanged

- GPT-5.6 Luna
- reasoning=none
- Jarvis personality/humor
- whole-response Qwen
- fixed Qwen seed
- final-only Whisper
- response-length policy
