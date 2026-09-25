# ISSUE-022 — Qwen full-reference clone runaway

## Status
Mitigated in 0.0.4-repair17; root-cause investigation deferred until after Voice Lab provider selection.

## Evidence
Using the same healthy saved reference and the same target diagnostic sentence:

- Qwen x-vector-only direct upstream clone generated clean speech in ~4.08 seconds.
- Qwen transcript-conditioned full-reference direct clone generated ~163.8 seconds of corrupted/runaway audio.

This isolates the failure to Qwen's transcript/reference conditioning path rather than the microphone, saved WAV, base model load, CUDA runtime, waveform serialization, or speaker playback.

## Mitigation
Normal Qwen Jarvis synthesis defaults to x-vector cloning. Full-reference conditioning remains diagnostic-only/explicit until it passes bounded-duration and listening acceptance.

## Future investigation
- verify exact reference transcript alignment and punctuation;
- test a professionally captured canonical reference set;
- compare newer Qwen releases/runtime combinations;
- measure whether full ICL materially improves identity/prosody enough to justify re-enabling it.
