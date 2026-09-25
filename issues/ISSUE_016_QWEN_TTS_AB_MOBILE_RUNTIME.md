# ISSUE-016 — Qwen3-TTS A/B and mobile runtime boundary

## Problem

Chatterbox Turbo is functional but warm first-waveform latency and prosody still
need comparison against another clone-capable local TTS. At the same time, a
desktop winner must not silently become a phone requirement.

## Repair11 decision

Add Qwen3-TTS 12Hz 0.6B Base as a parallel isolated TTS adapter and expose a
Voice Lab provider switch. Keep Chatterbox unchanged. The first Qwen test uses
the official Python/PyTorch runtime on CUDA with SDPA and the official Base
voice-cloning checkpoint.

## Mobile boundary

Do not claim the desktop Python runtime is phone-ready. A future mobile adapter
must independently pass storage, RAM, thermals, TTFA, RTF, cloning similarity,
and battery tests. Native/quantized Qwen runtimes are an optimization path, not
a launch assumption.
