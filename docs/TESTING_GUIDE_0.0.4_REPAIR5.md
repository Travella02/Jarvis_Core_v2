# Testing Guide - 0.0.4-repair5

1. Run the full automated suite:

```powershell
python -m unittest discover -s tests -v
```

2. Re-run the existing Chatterbox setup; do not delete the runtime first:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_chatterbox_runtime.ps1 -Profile modern-cuda
```

Expected behavior: the first missing model asset begins downloading instead of returning HTTP 404. Existing verified files are skipped; `.partial` files are resumed when present.

3. After setup completes:

```powershell
python -m apps.voice_lab --doctor
python -m apps.voice_lab --provider-health
```

Target: `model_assets_ready: true`, STT ready, and TTS ready on CUDA.

4. Do not clean patch/repair artifacts or commit until the full 0.0.4 live voice acceptance passes.
