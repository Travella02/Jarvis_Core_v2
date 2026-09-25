# Testing Guide - 0.0.4-repair6

1. Run the full automated suite:

```powershell
python -m unittest discover -s tests -v
```

2. No Chatterbox reinstall or model redownload is required. Confirm the existing local assets remain present:

```powershell
python -m apps.voice_lab --doctor
```

Target: Whisper server/model ready, Chatterbox runtime present, and `model_assets_ready: true`.

3. Retry the actual local provider load:

```powershell
python -m apps.voice_lab --provider-health
```

Target:

```text
STT: ready - local whisper.cpp server ready
TTS: ready - Chatterbox Turbo ready on cuda
```

4. If both providers are ready, enumerate devices and run the live Voice Lab:

```powershell
python -m apps.voice_lab --devices
python -m apps.voice_lab
```

5. Do not clean patch/repair artifacts or commit until the full 0.0.4 live voice acceptance passes.
