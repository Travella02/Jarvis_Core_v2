# 0.0.4-repair11 — Qwen3-TTS A/B Provider

This repair adds a second local TTS candidate without replacing Chatterbox:

- `Qwen3TTSProvider` behind the existing `TextToSpeechProvider` contract.
- Isolated `.runtime/voice/qwen3_tts/.venv` runtime.
- Official `Qwen3-TTS-12Hz-0.6B-Base` voice-cloning checkpoint.
- CUDA 12.8 / PyTorch 2.7.1 compatibility profile for RTX 50-series testing.
- SDPA first-test path; FlashAttention is deliberately not a setup dependency.
- Reusable Qwen clone prompt cached inside the persistent sidecar.
- Voice Lab `--tts-provider chatterbox|qwen3` A/B switch.
- Provider-neutral `--voice-ref`, `--voice-ref-text`, and `--voice-language` inputs.
- Mobile runtime explicitly deferred to a separately measured native/quantized
  provider implementation.

No Whisper, Luna, Conversation Core, permissions, tools, or Chatterbox runtime
behavior is replaced by this repair.
