# 0.0.4-repair1 live acceptance

1. Apply `0.0.4-repair1` from the existing 0.0.4 Voice Lab root.
2. Run `python -m unittest discover -s tests -v`.
3. Confirm CUDA is visible with `nvcc --version`.
4. Retry Whisper setup:
   `powershell -ExecutionPolicy Bypass -File .\scripts\setup_whisper_cpp.ps1 -Backend cuda`
5. The script must print a CUDA version, `CMake generator: Visual Studio 17 2022`, a VS 2022 installation path, and the CUDA toolset root before configure/build starts.
6. If VS 2022 C++ Build Tools are missing, the script must stop before CMake configure and give the explicit `winget` installation hint. If the toolkit lacks its Visual Studio integration files, it must instead tell you to rerun the CUDA installer with Visual Studio Integration selected.
7. On a configured machine, the build should use `.runtime\voice\whisper_cpp\build-cuda`, produce `bin\whisper-server.exe`, download/verify `ggml-large-v3-turbo-q5_0.bin`, and end with `Whisper runtime ready.`
8. Then resume the original 0.0.4 guide at Chatterbox setup and provider-health/live voice testing.

Do not commit or clean patch/repair artifacts until full 0.0.4 live acceptance passes.
