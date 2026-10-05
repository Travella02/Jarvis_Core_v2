# Testing Guide — 0.0.5 Repair5e

Focused regression:

`python -m unittest tests.unit.test_0_0_5_repair5e_speech_confidence tests.unit.test_0_0_5_repair5e_whisper_confidence tests.unit.test_0_0_5_lexical_speech tests.unit.test_0_0_5_barge_in_arm tests.unit.test_0_0_5_repair4_transcript_authority tests.unit.test_0_0_5_repair5_silero_presence tests.integration.test_0_0_5_continuous_session tests.integration.test_voice_lab_engine -v`

Expected in the verified candidate: 42 tests, OK.

Full regression:

`python -m unittest discover -s tests -v`

Expected in the verified candidate: 279 tests, OK.

## Live Voice Lab

Run:

`python -m apps.voice_lab --turns 8 --tts-provider qwen3-streaming --voice-profile tanner-test --input-device 1 --qwen-fixed-seed 12345 --tts-response-mode whole --stt-endpoint-final-only --luna-model gpt-6-luna --luna-service-tier default`

Startup should include multi-signal speech validation with no keyword fast paths.

Acceptance checks:
1. Stay silent 15-20 seconds: no accepted ghost user turn.
2. Rub/tap the microphone and sneeze: candidates may appear, but weak speech should be rejected rather than sent to Luna.
3. Give natural one-word replies such as `yes`, `no`, or `why`: clean speech should still be accepted.
4. Interrupt during thinking/synthesis: Jarvis should wait for confidence confirmation, then cancel the old turn and keep recording the same utterance.
5. Interrupt during speech: playback should stop only after speech confidence is confirmed; context/heard-prefix accounting should remain intact.
6. Verify rejected noise does not reset the 60-second inactivity timer.
7. Confirm all accepted speech still follows the normal Jarvis intelligence path.

Watch `Speech confirmed` and rejected-candidate telemetry. The component scores make threshold tuning evidence-driven if live data shows a consistent false-positive/false-negative pattern.
