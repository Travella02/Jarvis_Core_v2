# Testing Guide — 0.0.5 Repair5

## One-time VAD model setup

Repair5 adds a tiny local Silero VAD model. Install/verify it once:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_whisper_vad.ps1
```

Future full whisper.cpp setup runs also invoke this script automatically.

## Focused regression

```powershell
python -m unittest `
  tests.unit.test_0_0_5_repair5_silero_presence `
  tests.unit.test_0_0_5_barge_in_arm `
  tests.unit.test_0_0_5_repair4_transcript_authority `
  tests.unit.test_audio_input_validation_policy `
  tests.integration.test_0_0_5_continuous_session `
  tests.integration.test_0_0_5_interruption_context `
  tests.integration.test_voice_lab_engine -v
```

Then:

```powershell
python -m unittest discover -s tests -v
```

## Live command

```powershell
python -m apps.voice_lab --turns 8 `
  --tts-provider qwen3-streaming `
  --voice-profile tanner-test `
  --input-device 1 `
  --qwen-fixed-seed 12345 `
  --tts-response-mode whole `
  --stt-endpoint-final-only `
  --luna-model gpt-6-luna `
  --luna-service-tier default
```

Startup should include a line similar to:

`Speech presence: silero-v6.2.0 via whisper.cpp (threshold=0.50, authority=neural-speech-presence)`

## Acceptance sequence

1. Stay silent for at least 15 seconds while sleeping. There should be no ghost
   `Sleeping heard: Thank you.` / `Bye.` / `Wow.` user turns.
2. Say quietly: `Hey Jarvis, tell me something interesting about space.`
3. Ask `Why is that?` at normal/quiet conversational volume. It should become a
   real turn without an amplitude veto.
4. While Jarvis is still thinking/synthesizing, say
   `Actually, tell me about Mars instead.` Jarvis should cancel the prior turn
   on neural speech-start and use the full interruption transcript as the next turn.
5. While Jarvis is audibly speaking, say `Wait, explain that differently.`
   Playback should stop quickly and context should remain coherent.
6. Remain silent again. Jarvis must not reply to hallucinated silence transcripts.
7. End the session normally. There should be no `Task was destroyed but it is
   pending` or `cannot reuse already awaited coroutine` shutdown errors.

RMS/peak values may still appear in diagnostics. They are telemetry only and do
not authorize or reject user speech in the Repair5 continuous path.
