# 0.0.4 Repair24 — Resident streaming Qwen in Voice Lab

## Goal
Move the successful Repair23 resident Qwen benchmark into the actual Voice Lab path without replacing the accepted Repair20 Qwen provider.

## What changed
- Adds `Qwen3StreamingProvider`, an experimental `TextToSpeechProvider` backed by the isolated Repair22/23 Python 3.12 runtime.
- Adds one resident `live_sidecar.py` that loads Qwen once, prepares the active clone once, performs one hidden compile/warmup before listening, and then serves many synthesis requests.
- Streams PCM16 chunks over a framed binary stdio protocol rather than waiting for a complete WAV file.
- Adds the Voice Lab selector `--tts-provider qwen3-streaming`.
- Adds a provider-neutral startup PCM runway. The candidate requests 600 ms, which is normally two ~320 ms Qwen chunks. Synthesis begins immediately; only already-generated PCM is buffered.
- Keeps the existing `qwen3` provider available as the accepted fallback/A-B baseline.

## Why 600 ms
Repair23 measured hot first chunks around 133 ms, but chunk 2 arrived about 516–587 ms after chunk 1. Beginning playback after roughly two chunks gives Qwen a small lead over the speaker so the early chunk-2 jitter does not create a gap. This is intentionally different from Repair21: Repair24 does not wait for more text before synthesis.

## Startup behavior
The candidate still has a one-time model/voice/compile warmup cost. Voice Lab pays this before it starts listening, then the process stays resident for all requested turns. Startup optimization is a later task; Repair24 is testing the user-facing hot path.

## Acceptance gate
Do not commit yet. Run the five-turn Voice Lab session with `qwen3-streaming` and compare:
- speech end -> first audible audio
- TTS request -> first waveform
- first waveform -> startup buffer ready
- continuity after speech begins
- voice quality/prosody
