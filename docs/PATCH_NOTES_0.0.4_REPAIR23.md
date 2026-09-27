# Jarvis Core v2 0.0.4 Repair23 — Resident Qwen Warm-Request Benchmark

## Purpose
Repair22d proved that the experimental Qwen3-TTS fork can emit real PCM chunks
continuously once generation is underway. Repair23 measures the next question:
**how fast is the first PCM chunk when Qwen stays loaded, compiled, and resident?**

## Scope
Repair23 is additive and remains isolated from the accepted Repair20 provider.
It adds a resident benchmark only; it does not integrate the candidate into
Voice Lab or Jarvis's live TTS provider.

## Benchmark sequence
1. Load the candidate model once using SDPA.
2. Prepare the existing x-vector-only voice-clone prompt once.
3. Enable the candidate's streaming optimizations once.
4. Run one complete warmup synthesis in the same process and discard its audio.
5. Without exiting or reloading, run three measured syntheses.
6. Report first PCM chunk, first playback start, total generation, audio duration,
   RTF, and per-chunk arrival intervals for each measured request.

The warmup intentionally uses the same text as the measured requests. This
isolates the best-case hot path after model loading/compilation and avoids
confusing dynamic-shape recompilation with resident-request latency.

## Safety
- Does not overwrite any Repair20 or Repair22d source file.
- Does not modify `.env`, the main `.venv`, accepted Qwen model assets, or Git metadata.
- Reuses the already-installed isolated Repair22 candidate runtime.
- Installer aborts if the expected Repair22d worker is not present.

## Gate
Do not integrate the streaming candidate into Jarvis yet. First inspect
`RESIDENT_BENCHMARK_SUMMARY` and confirm hot first-chunk latency is suitable.
