# ISSUE-007 - Resilient local voice model downloads

## Observed

After repair1 successfully compiled whisper.cpp with CUDA 12.8/VS 2022, two consecutive attempts to download `ggml-large-v3-turbo-q5_0.bin` failed because PowerShell `Invoke-WebRequest` lost the underlying HTTPS connection while transferring the ~547 MiB model.

## Cause

The original 0.0.4 setup used a single non-resumable `Invoke-WebRequest` call directly into the final model path. A transient network/TLS failure therefore aborted setup, could leave a truncated final file, and forced another full attempt.

## Repair

0.0.4-repair2 makes model acquisition resumable and integrity-gated. `curl.exe` is primary, BITS is fallback, older partial bytes are recovered where possible, SHA-1 is verified before promotion, and the verified temp file is atomically moved to the final path.

## Long-term rule

Large local Jarvis assets must be downloaded through a provider-neutral installer path that tolerates interrupted connections and never exposes partial/corrupt assets as installed. Model/runtime installers should be replaceable independently from Voice Core.
