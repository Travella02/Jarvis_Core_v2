# 0.0.4-repair1 - CUDA/VS Toolchain Selection

Live Voice Lab setup exposed a Windows build-toolchain issue: CMake 4.4 can auto-select Visual Studio 2026 when it is the newest installed instance, while CUDA 12.8 supports the Visual Studio 2022/MSVC 193x toolchain.

Repair1 changes only the local whisper.cpp setup path and candidate metadata/tests. It:

- detects the installed CUDA Toolkit version through `nvcc`
- discovers a Visual Studio 2022 installation that actually contains x64 C++ tools
- explicitly configures CMake with `Visual Studio 17 2022`, `x64`, the discovered VS instance, and the installed CUDA toolkit root via CMake's `-T cuda=<path>` toolset selection
- uses backend-specific CMake build directories (`build-cuda` / `build-cpu`) so the failed VS 2026 cache cannot poison the retry
- clears an incompatible cache if one exists in the selected backend build directory
- validates the CUDA Visual Studio integration files inside the toolkit before CMake configure
- emits actionable VS 2022/CUDA integration guidance instead of a generic CMake failure
- leaves Whisper, Chatterbox, Conversation Core, Luna, and all provider boundaries unchanged

`VERSION` remains `0.0.4`; this is a same-version acceptance repair.
