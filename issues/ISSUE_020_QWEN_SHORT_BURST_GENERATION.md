# ISSUE_020 — Qwen voice clone generated 160 ms noise burst

## Observed

The provider-only Qwen diagnostic generated a 24 kHz WAV with only 3,840 samples (160 ms) for a full diagnostic sentence. The output was a short noise-like burst, so physical speaker playback was not the cause.

## Root-cause direction

Jarvis was accepting Qwen Base simulated-streaming voice-clone generation. Upstream Qwen work documents instability in this text-feed mode and recommends non-streaming generation for ordinary offline voice cloning.

## Repair

0.0.4-repair15 forces stable non-streaming clone generation and adds a duration sanity gate so implausibly short outputs fail closed.

## Acceptance

- Qwen provider-only diagnostic emits intelligible speech of plausible duration, or fails clearly instead of forwarding a short noise burst.
- Existing Chatterbox, Whisper, Luna, and provider-neutral voice contracts remain unaffected.
