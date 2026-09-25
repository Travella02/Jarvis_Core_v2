# Testing Guide — 0.0.4-repair17 Stable Qwen Clone Mode

## Automated regression

```powershell
python -m unittest discover -s tests -v
python -m apps.voice_benchmark
```

Expected: `151` tests / `OK` and Voice benchmark `6/6 passed`.

## Provider health

```powershell
python -m apps.voice_lab --provider-health --tts-provider qwen3
```

Expected: Qwen ready on CUDA.

## Isolated Qwen waveform test

Use the same saved profile that produced the clean repair16 x-vector diagnostic:

```powershell
python -m apps.voice_lab --tts-diagnostic `
  --tts-provider qwen3 `
  --voice-profile tanner-test `
  --tts-diagnostic-text "Jarvis voice diagnostic. This sentence should sound clear and natural."
```

Expected: the saved `tts_qwen3.wav` is intelligible speech and several seconds long, not a short burst and not a runaway multi-minute clip.

## End-to-end Voice Lab

```powershell
python -m apps.voice_lab --turns 3 `
  --tts-provider qwen3 `
  --voice-profile tanner-test `
  --input-device 1
```

Acceptance points:

- Whisper still transcribes correctly.
- Qwen speaks intelligibly with the saved voice identity.
- No transcript-conditioned runaway audio occurs.
- Warm-turn timing is captured for Qwen vs. Chatterbox comparison.

Do not clean/commit 0.0.4 until live acceptance is complete.
