# 0.0.4-repair2 Live Acceptance

1. Apply `apply_0.0.4_repair2.py` from the Jarvis Core v2 project root.
2. Run `python -m unittest discover -s tests -v`.
3. Rerun:

   `powershell -ExecutionPolicy Bypass -File .\scripts\setup_whisper_cpp.ps1 -Backend cuda`

4. The already-working CUDA/VS 2022 build path may perform an incremental build. During model acquisition, expect curl progress and either a fresh download or a message that an earlier incomplete model was preserved/resumed.
5. Success ends with `Whisper runtime ready.` and prints the local server/model paths.
6. Run `python -m apps.voice_lab --doctor`, then `python -m apps.voice_lab --provider-health`.
7. Continue with Chatterbox setup only after Whisper reports ready.

Do not clean patch/repair/backup artifacts or commit until all of 0.0.4 Voice Lab passes live acceptance.
