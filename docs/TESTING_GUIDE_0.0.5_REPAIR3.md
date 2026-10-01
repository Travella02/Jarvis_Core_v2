# Testing Guide — 0.0.5 Repair3

Focused regression:

`python -m unittest tests.unit.test_0_0_5_lexical_speech tests.unit.test_0_0_5_barge_in_arm tests.unit.test_speech_evidence tests.unit.test_audio_input_validation_policy tests.integration.test_0_0_5_continuous_session tests.integration.test_0_0_5_interruption_context tests.integration.test_voice_lab_engine -v`

Expected: 23 tests, OK.

Full regression:

`python -m unittest discover -s tests -v`

Expected for the verified Repair3 tree: 249 tests, OK.

## Live Voice Lab

Use the same 0.0.5 command:

`python -m apps.voice_lab --turns 8 --tts-provider qwen3-streaming --voice-profile tanner-test --input-device 1 --qwen-fixed-seed 12345 --tts-response-mode whole --stt-endpoint-final-only --luna-model gpt-6-luna --luna-service-tier default`

### Acceptance sequence

1. Wake with a full sentence:
   `Hey Jarvis, tell me something interesting about space.`

2. Speak a quiet normal follow-up:
   `Why is that?`
   It should be transcribed instead of rejected for low RMS/peak.

3. Stay silent while Jarvis answers.
   Noise/activity without lexical STT words must not interrupt his response.

4. Interrupt during thinking:
   `Actually, tell me about Mars instead.`

5. Interrupt during speaking:
   `Wait, explain that more simply.`

6. Try one-word controls:
   `Stop.`
   `Wait.`
   `Why?`

Expected behavior:
- raw activity may still appear in telemetry;
- only lexical confirmation causes barge-in;
- Jarvis's previous response can be interrupted before or during playback;
- the same user utterance continues to final STT and becomes the next turn;
- quiet legitimate words are not rejected solely because of amplitude;
- if no interruption occurs, Jarvis must synthesize and speak normally.
