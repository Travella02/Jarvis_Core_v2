# Testing Guide — 0.0.5 Realtime Conversation Control

## Install patch

From the project root after extracting the patch ZIP:

```powershell
python apply_0_0_5_patch.py
```

## Automated tests

Focused:

```powershell
python -m unittest tests.unit.test_0_0_5_wake_sleep_control tests.integration.test_0_0_5_interruption_context tests.integration.test_0_0_5_continuous_session -v
```

Expected focused summary: `Ran 8 tests` / `OK`.

Full regression:

```powershell
python -m unittest discover -s tests -v
```

Expected candidate summary before delivery: `Ran 236 tests` / `OK`.

## Live command

Use a headset for 0.0.5 acceptance because production AEC is not included yet.

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

## Manual acceptance sequence

1. Startup should say the controlled session starts `sleeping` and list wake/sleep phrases plus `idle_sleep=60s`.
2. While sleeping, say a sentence without Jarvis (for example, `What time is it?`). It should be locally heard/ignored and must not produce a Luna/TTS answer.
3. Say: `Hey Jarvis, tell me something interesting about space.` Jarvis should wake and answer that request immediately; you should not need to say `Jarvis` and then wait before asking.
4. Ask two follow-ups without saying the wake word. Jarvis should answer both and remain awake.
5. During a longer Jarvis answer, start speaking naturally. His playback should stop quickly after confirmed speech onset. Finish your interruption. The next turn should use it without losing topic/context.
6. Inspect the interrupted turn output. It should show `Status: interrupted`, playback bytes/unheard bytes, approximate playback milliseconds, and approximate heard text.
7. On the next Luna path, continuation should remain healthy when possible (`continuation=yes`, `reason=exact_chain`). The provider may show `input_items=2` because the private interruption note plus the new user message are both incremental input.
8. While Jarvis is speaking, say `That's all, Jarvis.` Playback should stop; after STT completes Jarvis should sleep without replying to the sleep command.
9. Wake him again with a full-sentence wake command and confirm conversation resumes.
10. Let Jarvis finish a response, then remain silent for 60 seconds. He should report sleeping. A non-wake utterance should then be ignored.

## Custom wake phrase experiment

Example:

```powershell
python -m apps.voice_lab --turns 3 `
  --wake-phrase computer `
  --wake-phrase "hey computer" `
  --tts-provider qwen3-streaming `
  --voice-profile tanner-test `
  --input-device 1 `
  --qwen-fixed-seed 12345 `
  --tts-response-mode whole `
  --stt-endpoint-final-only `
  --luna-model gpt-6-luna `
  --luna-service-tier default
```

Then `Computer, tell me a joke` should wake Jarvis; `Jarvis, tell me a joke` should not.

## Failure clues

- Jarvis interrupts himself while using open speakers: expected limitation until AEC; repeat with a headset.
- Wake phrase appears in the submitted prompt: wake stripping is broken.
- Follow-up requires another wake word: awake lifecycle is broken.
- Interruption stops playback but the microphone utterance is lost: capture and response cancellation were coupled incorrectly.
- Next Luna turn acts as if the full interrupted answer was heard: interruption metadata injection is broken.
- Jarvis sleeps while still speaking or while the user is mid-utterance: idle activity tracking is broken.
