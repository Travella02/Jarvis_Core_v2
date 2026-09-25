# 0.0.4-repair19 — Persistent Luna + Prosody-Safe First Clause

## Scope

Repair19 targets the remaining warm-turn latency without changing Jarvis authority boundaries.

- Voice Lab defaults Luna voice turns to a persistent Responses WebSocket transport.
- Conversation Core remains authoritative. The OpenAI adapter only uses `previous_response_id` when the next Core snapshot exactly extends the prior completed turn; any divergence resets to a full-context request.
- If the WebSocket cannot start before output begins, the provider falls back to the proven HTTP Responses path for that turn.
- Whisper runs one hidden local inference during startup so the user's first utterance does not pay CUDA/kernel cold-start cost.
- TTS chunking may emit one bounded, meaningful first comma-clause as a complete spoken sentence. Tiny openers such as `Well,` are not split.
- Voice telemetry now prints first spoken-chunk word/character count.

## Non-goals

- No change to permissions/tool authority.
- No change to the canonical conversation state model.
- No third-party Qwen streaming fork.
- No claim that 0.0.4 has reached final production latency; live acceptance is required.
