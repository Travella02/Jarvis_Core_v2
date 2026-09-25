# 0.0.4-repair11 live test — Qwen3-TTS A/B Provider

## Automated checks

```powershell
python -m unittest discover -s tests -v
python -m apps.voice_benchmark
python -m core.diagnostics
```

## Install Qwen runtime

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_qwen3_tts_runtime.ps1 -Profile modern-cuda
```

The runtime and ~2.5 GB official model snapshot stay under ignored
`.runtime\voice\qwen3_tts\`.

## Verify selected provider

```powershell
python -m apps.voice_lab --doctor
python -m apps.voice_lab --provider-health --tts-provider qwen3
```

## Reference clip

Use a clean 3–10 second WAV you have permission to clone. For the best first
comparison, provide the exact words spoken in that clip. Example:

```powershell
python -m apps.voice_lab --turns 3 --tts-provider qwen3 `
  --voice-ref "C:\path\reference.wav" `
  --voice-ref-text "This is the exact sentence spoken in my reference recording." `
  --voice-language English
```

For a quick transcript-free test only:

```powershell
python -m apps.voice_lab --turns 3 --tts-provider qwen3 `
  --voice-ref "C:\path\reference.wav" --qwen-xvector-only
```

Compare warm turns against Chatterbox using the same prompts/reference and record:

- `TTS request -> first waveform`
- speech-end -> first audible audio
- pronunciation/prosody
- clone similarity
- sentence-to-sentence consistency
- VRAM/RAM and startup time

Do not commit 0.0.4 until the A/B result and remaining Voice Lab acceptance are
reviewed.
