# Jarvis Core v2 0.0.4-repair10 — Audio Input Validation & False-Speech Rejection

This repair responds to live testing where a quiet room produced false turns such as `Thank you.` and clean headset speech was frequently mis-transcribed. It keeps Whisper large-v3-turbo-q5_0 as the STT candidate while validating the audio path before any provider decision.

## Changes

- Added provider-neutral `SpeechEvidenceGate` policy owned by ORVEX Voice Core.
- WebRTC VAD is now one signal rather than final authority.
- Candidate speech must pass duration, VAD-ratio, acoustic-energy, peak-level, and adaptive noise-floor checks.
- Rejected endpoint candidates never reach Whisper; the microphone session silently continues listening for real speech.
- Voice Lab prints ignored false candidates and why they were rejected.
- Added `--audio-diagnostic` to save three listenable stages from the selected device:
  - `1_raw_device.wav` — native headset/device PCM before Jarvis processing.
  - `2_resampled_16k.wav` — the exact 16 kHz resampled stream used by ORVEX VAD/STT input policy.
  - `3_whisper_input.wav` — only the exact endpointed candidate that passed evidence and would be sent to STT. If evidence rejects all candidates, this file is intentionally absent.
- Added `manifest.json` with device/backend/sample-rate and speech-evidence metrics.
- Added deterministic regression tests proving a short false VAD trigger is rejected before STT and listening continues to a later real utterance.

## Non-goals

- No STT provider swap.
- No spectral noise suppression or acoustic echo cancellation yet; 0.0.5 still owns the final full-duplex/AEC path.
- No cloud STT fallback/redundancy yet. Repair10 deliberately validates the microphone pipeline first so a future provider is not fed corrupted audio.
- No claim that the current evidence thresholds are final product values until live headset diagnostics are reviewed.
