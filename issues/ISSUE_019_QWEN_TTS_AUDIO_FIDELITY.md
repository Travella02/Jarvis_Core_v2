# ISSUE 019 — Qwen TTS Audio Fidelity / Playback Boundary

## Observed
Qwen3-TTS provider health was ready and synthesis completed, but the user heard noise-like/unintelligible output rather than speech.

## Risk
A local TTS model can appear healthy while either waveform serialization or host-device playback corrupts the audible result. Treating those as one stage makes provider comparisons unreliable.

## Repair14 decision
1. Use Qwen's official float waveform serialization route through libsndfile.
2. Validate waveform shape/finiteness before exposing it to Core.
3. Keep physical sample-rate adaptation in the ORVEX audio integration, not in Qwen/Chatterbox adapters.
4. Add provider-only WAV diagnostics so generated audio can be auditioned independently of PortAudio.

## Acceptance
The provider-only Qwen WAV must contain intelligible speech. The same speech must remain intelligible through the configured physical speaker output.
