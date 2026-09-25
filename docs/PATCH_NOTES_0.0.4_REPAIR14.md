# 0.0.4-repair14 — Qwen Audio Fidelity & Native Playback

## Why this repair exists

The Qwen3-TTS 0.6B Base sidecar loaded and synthesized successfully, but live Voice Lab playback produced unintelligible/noise-like audio instead of clear speech. The provider path therefore needed a clean separation between model waveform generation and physical speaker playback.

## Changes

- Qwen sidecar now serializes generated float waveforms using `soundfile.write(..., subtype="PCM_16")`, matching the official Qwen examples instead of manually assuming/scaling a waveform range.
- Qwen synthesis rejects empty, non-1D, or NaN/Inf waveforms and reports basic waveform peak/RMS metadata.
- `SoundDeviceAudioOutput` now adapts mono PCM16 provider audio to the selected output endpoint's native sample rate before opening/writing the physical stream. Provider/model sample rates remain provider-neutral.
- Playback accounting continues to use source/provider bytes so resampling cannot make the heard/unheard ledger lie.
- Voice Lab adds `--tts-diagnostic`, which writes the exact provider PCM stream to a WAV without speaker playback. This tells us whether corruption originates in Qwen generation/provider serialization or PortAudio/device playback.

## Scope

No STT, Luna policy, voice profile persistence, Qwen model weights, Chatterbox model behavior, or Conversation Core semantics are changed.
