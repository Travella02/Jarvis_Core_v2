# Jarvis Core v2 0.0.5 Repair5d — host-independent DLL-loader test

## Scope
Test-only repair. Runtime Jarvis behavior is unchanged.

## Why the focused test failed
`test_windows_loader_retries_with_winmode_zero` expected exactly one DLL search
directory handle. On a real Windows development machine, Repair5c correctly
discovers both Jarvis's whisper.cpp `bin` directory and one or more installed CUDA
`bin` directories. The unit test therefore saw multiple valid handles and failed.

## Fix
The fallback-loader test now mocks `_windows_dependency_directories()` to one
controlled temporary directory. CUDA discovery remains covered by the separate
dependency-discovery tests.

No production files are changed.
