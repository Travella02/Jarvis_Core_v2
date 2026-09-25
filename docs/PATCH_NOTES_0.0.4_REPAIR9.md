# Jarvis Core v2 0.0.4-repair9 — Natural Prosody & Warm Session Latency

This repair responds to repair8 live testing. It does not change the chosen providers.

## Changes

- Sentence-safe TTS chunking; ordinary speech is no longer hard-cut mid-clause at the old first-phrase character limit.
- A 220-character emergency cap remains for pathological unpunctuated output.
- Voice prompt asks Luna for a short, complete first sentence so prosody safety does not require a long wait.
- Voice requests set OpenAI text verbosity to `low`; reasoning remains `none` with no automatic reasoning escalation.
- Chatterbox generation runs under `torch.inference_mode()` to remove autograd bookkeeping.
- Voice Lab supports `--turns N` so multiple turns reuse the same Conversation Core, OpenAI provider/client, Whisper server, and Chatterbox sidecar.
- Updated deterministic benchmark and regression coverage.

## Non-goals

- No provider swap.
- No Fast/Priority OpenAI service tier (it can change cost; default remains standard/auto service).
- No full-duplex microphone/AEC/barge-in; those remain 0.0.5 work.
- No claim that repair9 reaches the final latency target until measured live.
