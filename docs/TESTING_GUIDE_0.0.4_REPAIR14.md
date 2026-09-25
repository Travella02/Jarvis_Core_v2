# Testing 0.0.4-repair14

1. Run the automated suite and Voice benchmark.
2. Confirm Qwen provider health remains ready.
3. Generate a Qwen provider-only WAV without speaker playback:

```powershell
python -m apps.voice_lab --tts-diagnostic `
  --tts-provider qwen3 `
  --voice-profile tanner-test `
  --tts-diagnostic-text "Jarvis voice diagnostic. This sentence should sound clear and natural."
```

Listen to the printed `tts_qwen3.wav` path.

- If this WAV is clear speech, Qwen generation/provider serialization is healthy; proceed to the live speaker test.
- If this WAV itself is noise/garbled, do not blame PortAudio. Preserve the WAV and sidecar stderr for the next repair.

4. Run the live Qwen session:

```powershell
python -m apps.voice_lab --turns 3 --tts-provider qwen3 --voice-profile tanner-test --input-device 1
```

The selected HyperX MME microphone remains the accepted STT input baseline. Speaker playback should now open at the physical output endpoint's native rate while provider audio is resampled locally.

Do not clean/commit until live acceptance is complete.
