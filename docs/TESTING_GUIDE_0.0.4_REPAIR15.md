# Testing 0.0.4-repair15

Run from the Jarvis_Core_v2 project root with the project venv active.

## 1. Automated regression

```powershell
python -m unittest discover -s tests -v
python -m apps.voice_benchmark
```

Expected: 147 tests pass and Voice benchmark is 6/6.

## 2. Provider health

```powershell
python -m apps.voice_lab --provider-health --tts-provider qwen3
```

## 3. Qwen provider-only diagnostic

```powershell
python -m apps.voice_lab --tts-diagnostic `
  --tts-provider qwen3 `
  --voice-profile tanner-test `
  --tts-diagnostic-text "Jarvis voice diagnostic. This sentence should sound clear and natural."
```

The diagnostic prints generated duration. A complete sentence should no longer be accepted as a ~160 ms clip. Listen to tts_qwen3.wav before speaker playback.

If generation is still implausibly short, the command should fail clearly instead of reporting success.

## 4. Live Qwen candidate

```powershell
python -m apps.voice_lab --turns 3 `
  --tts-provider qwen3 `
  --voice-profile tanner-test `
  --input-device 1
```

Do not clean patch/backup artifacts or commit 0.0.4 until live acceptance passes.
