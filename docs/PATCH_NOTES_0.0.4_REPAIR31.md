# Jarvis Core v2 0.0.4 Repair31 — Fixed-Seed Separate-Sentence A/B

Repair30 changed Qwen sampling temperatures and produced severe audio corruption.
Repair31 does not change Qwen's generation parameters at all.

## Goal
Keep the committed Repair27 architecture:
- separate sentence/chunk synthesis for fast first response;
- resident true-streaming Qwen;
- x-vector-only voice clone;
- original upstream Qwen sampling settings.

Then optionally make each separate synthesis request begin from the same random
number generator state.

## Behavior
Default (no CLI option):
- identical to Repair27;
- no RNG reset;
- original stochastic behavior.

A/B candidate:
`--qwen-fixed-seed 12345`

Before every *live synthesize request*, the isolated sidecar resets:
- Python `random`
- NumPy RNG
- PyTorch CPU RNG
- PyTorch CUDA RNG(s)

It does not pass temperature/top-k/top-p/do-sample overrides to Qwen.

## Why
If sentence-to-sentence delivery variation is primarily caused by starting each
Qwen request from a different stochastic state, resetting the same seed may make
cadence/timbre more repeatable while preserving Repair27 latency.

## Safety
This is explicitly optional. If the fixed-seed run sounds worse, omit the flag
and Jarvis behaves like committed Repair27.
