# ISSUE-006 - CUDA / Visual Studio toolchain selection

## Observed

On Windows with CMake 4.4, Visual Studio 2026 Build Tools, and CUDA 12.8 installed, the original 0.0.4 Whisper setup let CMake select the newest Visual Studio generator. CMake found CUDA 12.8 but failed with `No CUDA toolset found`.

## Cause

CUDA 12.8 supports Visual Studio 2022/MSVC 193x on Windows. The automatically selected Visual Studio 2026/v145 toolchain is outside that CUDA 12.8 support matrix. CMake generator choices are also cached per build tree.

## Repair

0.0.4-repair1 explicitly discovers and selects a VS 2022 C++ instance for CUDA builds, points CMake at the installed CUDA toolkit and its integration files through the Visual Studio toolset selector, and moves each backend into a separate build directory.

## Long-term rule

Provider runtime setup must select a known-compatible native toolchain deliberately. Do not equate "newest installed compiler" with "compatible compiler". Future CUDA/toolchain changes should update this setup adapter and its tests without changing Voice Core or the STT contract.
