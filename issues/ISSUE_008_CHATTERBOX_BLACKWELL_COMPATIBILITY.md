# ISSUE 008 - Chatterbox Blackwell Runtime Compatibility

## Observation

On the RTX 50-series development machine, Chatterbox 0.1.7 imported successfully in an isolated PyTorch 2.11 + cu128 runtime but its sidecar exited during `ChatterboxTurboTTS.from_pretrained(device="cuda")`. The original adapter discarded stderr, so provider-health could only report exit code 1.

## Risk

A provider runtime that imports successfully but fails at model load can look configured while remaining unusable. Using a PyTorch release much newer than the model's tested dependency surface also increases compatibility uncertainty.

## Repair3 decision

- keep TTS fully isolated from Jarvis Core
- use PyTorch/Torchaudio 2.7.1 + cu128 as the initial Blackwell compatibility profile
- retain Chatterbox 0.1.7 as a replaceable provider candidate
- validate CUDA with an actual tensor operation during setup
- preserve sidecar stderr/tracebacks and surface bounded startup diagnostics
- keep failure contained to the Chatterbox adapter so replacing TTS later requires no Conversation Core changes

## Exit condition

Close only after provider-health loads Chatterbox Turbo successfully on the target Blackwell machine and a real synthesis turn completes. If the provider remains unstable after measured repair attempts, evaluate a different local TTS adapter rather than coupling Core to Chatterbox-specific workarounds.
