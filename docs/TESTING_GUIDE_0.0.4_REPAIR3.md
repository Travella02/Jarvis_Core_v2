# 0.0.4-repair3 Live Acceptance

1. Apply `apply_0.0.4_repair3.py` from the existing 0.0.4-repair2 project root.
2. Run `python -m unittest discover -s tests -v`.
3. Re-run the isolated Chatterbox setup so the existing runtime is aligned to the repair3 compatibility profile:

   `powershell -ExecutionPolicy Bypass -File .\scripts\setup_chatterbox_runtime.ps1 -Profile modern-cuda`

4. Setup must report PyTorch/Torchaudio 2.7.1 + cu128, `cuda=True`, the NVIDIA device name, `chatterbox import=ok`, and `cuda-smoke=1.0`.
5. Run `python -m apps.voice_lab --doctor`; Whisper/model paths and Chatterbox runtime Python must still exist.
6. Run `python -m apps.voice_lab --provider-health`.
7. Success is:

   - `STT: ready - local whisper.cpp server ready`
   - `TTS: ready - Chatterbox Turbo ready on cuda`

8. If TTS still fails, do not guess. The provider-health line now includes the sidecar error/log tail, and the full traceback is stored at `.runtime\voice\chatterbox\logs\sidecar-stderr.log`. Send that output before another repair.
9. Only after both providers are ready, continue to `python -m apps.voice_lab --devices` and one real `python -m apps.voice_lab` turn.

Do not clean repair/patch/backup artifacts or commit until full 0.0.4 Voice Lab live acceptance passes.
