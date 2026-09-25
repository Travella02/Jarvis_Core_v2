# ISSUE 024 — Persistent Luna and First-Clause Latency

## Observation

Repair18 live testing showed Conversation Core overhead near tens of milliseconds, warm Luna TTFT generally sub-second, and Qwen synthesis strongly correlated with first-chunk length. First-turn Whisper inference also showed a cold-start penalty that disappeared on later turns.

## Decision

Test two provider-neutral latency improvements before considering a V1 rollback:

1. Persistent Responses WebSocket transport for voice continuation, guarded by exact Conversation Core snapshot-chain validation and HTTP fallback.
2. One prosody-safe, bounded first comma-clause for earlier TTS start, plus hidden Whisper inference warmup.

## Rollback criterion

If repeated warm live tests still cannot approach the established 1–2 second conversational target without unacceptable prosody/accuracy regressions, compare continuing V2 against resuming V1 and selectively backporting V2 architecture. Do not continue repair loops indefinitely.
