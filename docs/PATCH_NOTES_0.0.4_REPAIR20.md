# 0.0.4-repair20 — Whisper Warmup Runtime Fix

Repair19 added a real hidden Whisper inference warmup so the first user turn does not pay CUDA/kernel startup cost. Live acceptance exposed a missing `CorrelationContext` import inside the Whisper provider warmup path, causing Voice Lab startup to stop with `NameError` before the WebSocket/Luna test could begin.

Repair20 adds the missing import and a regression test that executes the warmup path with local I/O stubbed, proving it can build the hidden 16 kHz PCM frame without touching the real Whisper server.

No STT model, Qwen model, Luna policy, audio device setting, or runtime asset changes are included.
