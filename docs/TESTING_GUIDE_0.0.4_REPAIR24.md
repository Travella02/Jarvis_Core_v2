# Repair24 testing guide

1. Run the Repair24-specific tests.
2. Run the full unit/integration discovery suite.
3. Start the same five-turn Voice Lab session used for Repair20/21, but select `qwen3-streaming`.
4. Allow the one-time resident Qwen warmup to finish before speaking.
5. Listen specifically for uninterrupted speech after playback begins.

Command:

```powershell
python -m apps.voice_lab --turns 5 `
  --tts-provider qwen3-streaming `
  --voice-profile tanner-test `
  --input-device 1
```

Do not commit/clean until the five live turns are accepted.
