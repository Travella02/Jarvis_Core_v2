# 0.0.4-repair16 — Qwen Reference & Upstream Clone Diagnostics

This repair does not claim to fix Qwen generation. It adds a provider-specific diagnostic that determines whether the current short-burst failure comes from the saved reference clip/transcript, Qwen's official Base clone call, or Jarvis's cached/optimized provider path.

## Added
- Reference WAV signal/format validation inside the isolated Qwen runtime.
- Direct upstream-style full-reference clone smoke test.
- Direct x-vector-only clone smoke test.
- Saved diagnostic WAVs under ignored `.runtime/voice/diagnostics/`.
- Provider methods used only by Voice Lab diagnostics.
- Canonical ORVEX Jarvis voice identity recorded as provider-independent architecture.

## Unchanged
- Chatterbox remains the current default TTS candidate.
- Normal Qwen synthesis remains behind `TextToSpeechProvider`.
- Whisper, Luna, microphone selection, playback, user voice library and model assets are unchanged.
