# 0.0.4-repair17 — Stable Qwen Clone Mode

Live repair16 diagnostics produced a decisive split from the same saved reference:

- `qwen_upstream_xvector.wav`: clean/intelligible, ~4.08 seconds.
- `qwen_upstream_full.wav`: runaway/corrupted, ~163.8 seconds for the same short target sentence.

This proves the saved reference audio and base Qwen runtime are usable while the transcript-conditioned clone path is not accepted for normal Jarvis synthesis.

## Changes

- Normal Qwen3-TTS Base synthesis defaults to x-vector cloning regardless of whether the `VoiceProfile` stores a reference transcript.
- Stored transcript metadata is retained and unchanged for diagnostics/future enrollment quality work.
- Full-reference conditioning requires an explicit provider setting and is not selected by normal Voice Lab/profile usage.
- Cached Qwen prompts key against the effective clone mode so a full-reference prompt can never leak into the x-vector production path.
- The upstream A/B clone diagnostic remains unchanged so the full path can be revisited deliberately later.
- The official Jarvis voice identity remains above the concrete TTS provider.

## Unchanged

- Qwen model/runtime files.
- Saved voice reference audio and profile metadata.
- Whisper STT.
- Luna intelligence.
- Chatterbox baseline provider.
- Audio capture/playback.
- Voice reference persistence format.
