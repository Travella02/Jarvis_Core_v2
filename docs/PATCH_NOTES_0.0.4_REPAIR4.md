# 0.0.4-repair4 - Deterministic Chatterbox Model Assets

Live repair3 testing proved PyTorch 2.7.1 + CUDA 12.8 works on the RTX 5080 Laptop GPU, but Chatterbox then failed in Hugging Face `snapshot_download()` with `WinError 10054` while locating/downloading the Turbo model snapshot.

Repair4 keeps the working Blackwell runtime and changes only Chatterbox model delivery/startup:

- setup prefetches the exact Turbo files Jarvis uses into `.runtime/voice/chatterbox/models/chatterbox-turbo`
- `curl.exe` uses retry/resume for interrupted large-file transfers, with a Windows BITS fallback
- critical weight files are SHA-256 verified before atomic installation
- setup avoids downloading the unused legacy `s3gen.safetensors`, reducing the Jarvis Turbo asset set by roughly 1 GiB compared with Chatterbox's broad `*.safetensors` snapshot pattern
- the sidecar now calls `ChatterboxTurboTTS.from_local()` with an explicit provider-owned model directory
- provider-health/model startup becomes local/offline after setup instead of initiating a Hugging Face download
- `JARVIS_CHATTERBOX_MODEL_DIR` preserves an explicit replacement/override seam
- Voice Lab doctor reports whether the required local TTS assets are present without loading the model or using the network

`VERSION` remains `0.0.4`. Whisper, Luna, Conversation Core, Voice Core contracts, and the repair3 Torch/CUDA compatibility profile are unchanged.
