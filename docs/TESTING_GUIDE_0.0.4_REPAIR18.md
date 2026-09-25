# Testing Guide — 0.0.4-repair18

## Automated

```powershell
python -m unittest discover -s tests -v
python -m apps.voice_benchmark
```

Expected automated tests: **155**.

## Luna latency isolation

Run standard/default project processing first:

```powershell
python -m apps.luna_latency_probe --rounds 4
```

Record:
- raw Luna TTFT average;
- Conversation Core TTFT average;
- apparent Core/app overhead.

Then optionally test Fast mode:

```powershell
python -m apps.luna_latency_probe --rounds 4 --service-tier fast
```

This is an A/B test only. Do not make Fast mode the default until latency and cost are both accepted.

## Qwen warm-session test

```powershell
python -m apps.voice_lab --turns 5 `
  --tts-provider qwen3 `
  --voice-profile tanner-test `
  --input-device 1
```

Before the first `Listening...`, Voice Lab should print:
- `TTS inference warmup completed ...`
- `Luna connection warmup completed ...`

Compare turns 2–5, especially:
- STT final -> Luna first text
- TTS request -> first waveform
- speech end -> first audible audio

## Acceptance

Repair18 passes only if:
- all automated tests pass;
- Voice benchmark passes;
- the hidden prewarm completes before listening;
- raw Luna TTFT can be compared to Conversation Core TTFT;
- Qwen still produces intelligible speech with the accepted x-vector clone mode;
- no provider/runtime is made non-swappable.
