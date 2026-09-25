# 0.0.4-repair4 Live Acceptance

1. Apply `apply_0.0.4_repair4.py` from the existing 0.0.4-repair3 project root.
2. Run `python -m unittest discover -s tests -v`.
3. Re-run the Chatterbox setup:

   `powershell -ExecutionPolicy Bypass -File .\scripts\setup_chatterbox_runtime.ps1 -Profile modern-cuda`

4. The already-working Torch/CUDA checks must still report PyTorch 2.7.1 + cu128, `cuda=True`, the RTX device, `chatterbox import=ok`, and `cuda-smoke=1.0`.
5. Setup then downloads the provider-owned Chatterbox Turbo assets. Large files must retry/resume through curl; BITS is a fallback. Critical weights must verify SHA-256 before final installation.
6. Setup success must print `chatterbox-model-assets=ready`, tokenizer size 50276, and the local model directory.
7. Run `python -m apps.voice_lab --doctor`. `runtime_python_exists` and `model_assets_ready` must both be `true`.
8. Run `python -m apps.voice_lab --provider-health`.
9. Success is:
   - `STT: ready - local whisper.cpp server ready`
   - `TTS: ready - Chatterbox Turbo ready on cuda`
10. Only after both providers are ready, run `python -m apps.voice_lab --devices` and one real `python -m apps.voice_lab` turn.

Do not clean patch/repair/backup artifacts or commit until the full 0.0.4 Voice Lab passes live acceptance.
