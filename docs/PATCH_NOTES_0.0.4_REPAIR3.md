# 0.0.4-repair3 - Blackwell Chatterbox Runtime Compatibility

Live provider-health testing proved the local Whisper CUDA path is ready, but the isolated Chatterbox sidecar exited while loading the TTS model on an RTX 50-series/Blackwell machine. The previous `modern-cuda` profile used PyTorch 2.11 + CUDA 12.8, which is much newer than Chatterbox 0.1.7's upstream Torch 2.6 pin and provided no useful traceback because sidecar stderr was discarded.

Repair3 remains inside the Chatterbox adapter/runtime boundary. It:

- changes the Blackwell compatibility profile to PyTorch/Torchaudio 2.7.1 + CUDA 12.8, a much narrower step above Chatterbox's upstream Torch 2.6 baseline while retaining Blackwell support
- force-aligns the isolated `torch` and `torchaudio` versions on rerun so an existing 2.11 runtime is corrected in place
- performs a real one-tensor CUDA smoke test during setup
- keeps Chatterbox installed without its Torch pins so Jarvis Core's main environment remains untouched
- prevents third-party startup/generation chatter from corrupting the JSON-line sidecar protocol
- catches model-load exceptions as a structured `startup_error` message
- preserves the complete sidecar stderr/traceback under `.runtime/voice/chatterbox/logs/sidecar-stderr.log`
- includes a bounded log tail directly in provider-health failures instead of reporting only an exit code

`VERSION` remains `0.0.4`; this is a same-version live-acceptance repair. Whisper, Conversation Core, Luna, and all provider-neutral voice contracts are unchanged.
