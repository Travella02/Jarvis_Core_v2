# ISSUE_023 — Luna and Qwen latency boundaries

## Status

Open during 0.0.4 live acceptance.

## Evidence

Live Voice Lab testing showed:
- Whisper finalization is already fast after fixing microphone selection.
- Warm Luna TTFT remains roughly 1.3–1.5 seconds in the full voice path.
- Qwen x-vector cloning works, but current full-phrase generation can add another ~1.5–2.3 seconds before first waveform.
- Cold Qwen generation is substantially slower than later turns.

## Repair18 response

- Add a direct Luna TTFT probe to distinguish provider/network latency from Jarvis overhead.
- Reduce voice-only output cap.
- Add prompt-cache configuration for growing sessions.
- Add optional Fast mode A/B.
- Prewarm Luna connection and real TTS inference before listening.
- Tighten Qwen phrase token budget.

## Deferred

The accepted Qwen Python package does not expose a stable, already-approved incremental audio generator through the current Jarvis sidecar. Do not silently swap to a third-party streaming fork. Evaluate that runtime separately if full-phrase Qwen latency remains above the product target.
