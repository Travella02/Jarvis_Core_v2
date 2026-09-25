# 0.0.4-repair2 - Resilient Voice Model Downloading

Live Voice Lab setup proved the repair1 CUDA/Visual Studio toolchain fix: whisper.cpp built successfully with CUDA 12.8 and Visual Studio 2022. The remaining failure was the one-shot PowerShell `Invoke-WebRequest` used to download the ~547 MiB `large-v3-turbo-q5_0` model; the HTTPS connection closed unexpectedly on repeated attempts.

Repair2 changes only the Whisper model acquisition path and candidate metadata/tests. It:

- removes the one-shot `Invoke-WebRequest` model download
- uses Windows `curl.exe` as the primary downloader with redirects, retries, transient-error retries, and resume support
- preserves a truncated model left by earlier 0.0.4 attempts as a resumable `.partial` file
- handles servers that reject range resume by restarting cleanly
- falls back to Windows BITS if curl cannot complete
- verifies the published SHA-1 before the model is promoted to its final path
- retries exactly once from byte zero if a resumed file fails checksum validation
- installs the verified model atomically so Jarvis never treats a partial file as ready
- keeps the repair1 Visual Studio 2022/CUDA 12.8 toolchain selection unchanged

`VERSION` remains `0.0.4`; this is a same-version live-acceptance repair.
