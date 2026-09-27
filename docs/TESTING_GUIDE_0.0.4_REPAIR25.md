# Testing Guide — 0.0.4 Repair25

1. Run focused tests:
   `python -m unittest tests.unit.test_qwen3_streaming_voice_lab tests.unit.test_qwen3_streaming_low_latency_start -v`

2. Run the full suite:
   `python -m unittest discover -s tests -v`

3. Run the same five-turn Voice Lab:
   `python -m apps.voice_lab --turns 5 --tts-provider qwen3-streaming --voice-profile tanner-test --input-device 1`

Prompts:
1. Jarvis, tell me something interesting about space.
2. Why does that happen?
3. Explain it more simply.
4. Tell me another interesting fact.
5. Tell me a short joke.

Acceptance:
- No new mid-response gaps, clicks, or cut-off words.
- `first waveform -> startup buffer ready` should collapse toward 0 ms because
  the first normal PCM frame already exceeds the 250 ms runway.
- Compare `speech end -> first audible audio` with Repair24.
- Do not commit until live acceptance.
