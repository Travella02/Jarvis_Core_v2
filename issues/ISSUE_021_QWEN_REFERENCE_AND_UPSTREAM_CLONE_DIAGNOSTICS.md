# ISSUE 021 — Qwen Reference and Upstream Clone Diagnostics

## Status
Open during 0.0.4 live acceptance.

## Observed
Qwen3-TTS 0.6B Base repeatedly returned only ~160 ms of noise-like output for a normal sentence. Repair15 correctly rejected the clip, proving the failure occurs before speaker playback.

## Risks
A poor reference clip, mismatched transcript, ICL/reference-code conditioning problem, or runtime/model incompatibility could all produce similar symptoms. Changing normal Jarvis playback or chunking without isolating these causes would be guesswork.

## Repair16 scope
- Validate reference duration, sample rate, channels, level, clipping and near-silence.
- Run the official direct `generate_voice_clone(ref_audio=..., ref_text=...)` path without cached prompts.
- Run x-vector-only cloning with the same clip.
- Save both diagnostic WAVs for listening.
- Do not change the production Qwen synthesis path based on assumptions; use the diagnostic result first.
