# 0.0.4-repair6 - Chatterbox Local Loader API Compatibility

This repair is intentionally narrow. Whisper/CUDA, model asset delivery, the Blackwell PyTorch runtime, Voice Core, Conversation Core, and Luna are unchanged.

## Fix
Live provider-health testing reached the local Chatterbox model loader and exposed an API-version mismatch: the installed `chatterbox-tts==0.1.7` release accepts `ChatterboxTurboTTS.from_local(ckpt_dir, device)`, while newer upstream code also accepts a `nano` selector. The Jarvis Turbo adapter had passed `nano=False` explicitly and therefore crashed on 0.1.7.

Repair6 calls the common Turbo-compatible signature without the optional `nano` argument. This works for the installed 0.1.7 release and remains compatible with newer upstream versions where `nano` defaults to false.

## Preserved behavior
- Chatterbox Turbo remains the selected TTS candidate.
- local/offline `from_local()` startup remains mandatory after asset setup.
- pinned local model assets and checksums remain unchanged.
- PyTorch/Torchaudio 2.7.1 + cu128 isolation remains unchanged.
- Whisper large-v3-turbo-q5_0 remains unchanged.
