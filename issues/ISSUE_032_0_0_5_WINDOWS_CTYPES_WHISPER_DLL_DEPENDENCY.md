# ISSUE 032 — Python ctypes cannot resolve whisper.dll dependency on Windows

## Observed
The root `.runtime/voice/whisper_cpp/bin/whisper.dll` exists, but Voice Lab fails:

`Could not find module ... whisper.dll (or one of its dependencies)`

## Cause
Python 3.8+ uses a restricted Windows DLL dependency search for `ctypes`. The
whisper.cpp CUDA executable can run normally while loading the same shared library
inside Python fails to find transitive CUDA DLLs.

## Repair5c
Add explicit controlled DLL search directories for the Jarvis runtime and CUDA
Toolkit, then use an absolute-path `winmode=0` compatibility retry if needed.
