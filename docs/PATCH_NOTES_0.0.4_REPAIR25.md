# Jarvis Core v2 0.0.4 Repair25 — Low-Latency Streaming Start

## Goal
Reduce time from the first resident-Qwen PCM frame to playback without changing
the accepted Repair24 resident streaming architecture.

## Change
- Qwen streaming candidate startup PCM runway: 600 ms -> 250 ms.
- The 250 ms threshold is intentionally below the ~319-320 ms PCM chunks measured
  in Repair23, so a normal first PCM chunk releases immediately.
- Adds metadata identifying the strategy as `single-frame-fast-start`.
- Adds focused regression coverage.

## Why this is different from Repair21
Repair25 does not wait for more Luna text and does not make text chunks larger.
Qwen starts synthesis at the same time as Repair24. We simply stop waiting for a
second PCM chunk before handing already-generated audio to the speaker path.

## Risk / live acceptance
A one-frame runway is more aggressive. Listen specifically for an early pause,
click, or underrun between the first and second audio chunks. If continuity
regresses, reject Repair25 and return to Repair24's 600 ms runway.

## Untouched
- Repair20 accepted provider
- Whisper / Luna
- resident sidecar/model settings
- voice reference behavior
- `.env`, `.venv`, model assets, Git metadata
