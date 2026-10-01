# Testing Guide — 0.0.5 Repair1

Focused:

`python -m unittest tests.unit.test_0_0_5_qwen_resident_cancel tests.unit.test_0_0_5_barge_in_arm tests.integration.test_0_0_5_continuous_session -v`

Full:

`python -m unittest discover -s tests -v`

Live command is unchanged from 0.0.5:

`python -m apps.voice_lab --turns 8 --tts-provider qwen3-streaming --voice-profile tanner-test --input-device 1 --qwen-fixed-seed 12345 --tts-response-mode whole --stt-endpoint-final-only --luna-model gpt-6-luna --luna-service-tier default`

First verify the exact failing path:
1. Say a sentence without a wake phrase; it should be ignored.
2. Say `Hey Jarvis, tell me something interesting about space.`
3. Jarvis should wake and answer instead of reporting a sidecar exit.

Then verify barge-in:
4. Ask a longer follow-up.
5. Wait until Jarvis is audibly speaking, then interrupt him.
6. Playback should stop quickly; the same microphone capture should finish your
   interruption and become the next turn.
7. The next Jarvis response should not incur a Qwen cold reload/voice-prepare
   cycle. Resident Qwen must remain hot after normal barge-in.
