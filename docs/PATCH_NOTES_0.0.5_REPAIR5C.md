# Jarvis Core v2 0.0.5 Repair5c — Windows whisper.dll dependency loading

## Symptom
After the Silero model installed successfully, Voice Lab failed before startup with:

`Could not find module ...\whisper.dll (or one of its dependencies)`

The root `whisper.dll` exists. The failure is Windows dependency resolution inside
Python `ctypes`, most commonly the CUDA runtime dependencies used by the CUDA
whisper.cpp build.

## Fix
- explicitly adds the Jarvis whisper.cpp bin directory to Python's DLL search;
- discovers the active CUDA Toolkit from `CUDA_PATH` / `CUDA_PATH_V*`;
- adds the CUDA `bin` directory to the controlled DLL search;
- keeps those search-directory handles alive for the native VAD lifetime;
- retries the absolute DLL path with `winmode=0` only if the secure Python 3.8+
  loader cannot resolve a transitive dependency;
- emits a detailed dependency/search diagnostic if both loads fail.

No wake/sleep, interruption policy, STT text handling, TTS, or Luna behavior changed.
