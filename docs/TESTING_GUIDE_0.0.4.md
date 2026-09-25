# 0.0.4 Voice Lab live acceptance

1. Apply the root-safe patch.
2. Install main lightweight dependencies: `python -m pip install -r requirements.txt`.
3. Run all automated tests and `python -m apps.voice_benchmark`.
4. Run `python -m apps.voice_lab --doctor` before downloading models.
5. Set up whisper.cpp: `powershell -ExecutionPolicy Bypass -File .\scripts\setup_whisper_cpp.ps1 -Backend cuda`.
6. Set up Chatterbox: `powershell -ExecutionPolicy Bypass -File .\scripts\setup_chatterbox_runtime.ps1 -Profile modern-cuda`.
7. Run `python -m apps.voice_lab --doctor` again, then `python -m apps.voice_lab --provider-health`.
8. List devices with `python -m apps.voice_lab --devices` if device selection is needed.
9. Run one real turn: `python -m apps.voice_lab`.
10. Listen for STT accuracy, endpoint timing, TTS quality/naturalness, and note the latency marks.
11. Optional clone test: provide a consented local WAV with `--voice-ref "path\to\reference.wav"`.

Do not commit or clean patch artifacts until live acceptance passes.
