# 0.0.4-repair15 — Stable Qwen Voice-Clone Generation

## Why this repair exists

The provider-only Qwen diagnostic produced a 24 kHz WAV containing only 3,840 samples (160 ms) for a complete diagnostic sentence. The file itself contained a short noise-like burst, proving the failure occurred inside Qwen generation before Windows playback.

Qwen Base currently defaults to simulated-streaming text input. Jarvis repair15 forces stable non-streaming voice-clone generation for complete prosody-safe phrases.

## Changes

- Force non_streaming_mode=True for Qwen Base voice cloning.
- Keep do_sample=True and max_new_tokens=8192 explicit.
- Reject implausibly short generated audio instead of forwarding noise to playback.
- Report generated WAV duration in --tts-diagnostic.
- Keep Chatterbox as the default TTS; Qwen remains an A/B candidate.

## Non-goals

No Whisper, Luna, microphone, physical playback, model-asset, voice-library, or Chatterbox changes.
