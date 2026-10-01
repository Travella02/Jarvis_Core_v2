# Testing Guide — 0.0.5 Repair4

Focused regression (verified Repair4 tree: 34 tests):

`python -m unittest tests.unit.test_0_0_5_repair4_transcript_authority tests.unit.test_0_0_5_lexical_speech tests.unit.test_0_0_5_barge_in_arm tests.unit.test_repair34a_whisper_flag_wiring tests.unit.test_repair34_whisper_endpoint_final_only tests.unit.test_audio_input_validation_policy tests.integration.test_0_0_5_continuous_session tests.integration.test_0_0_5_interruption_context tests.integration.test_voice_lab_engine -v`

Full regression (verified Repair4 tree: 255 tests):

`python -m unittest discover -s tests -v`

## Live Voice Lab

Use the established 0.0.5 command:

`python -m apps.voice_lab --turns 8 --tts-provider qwen3-streaming --voice-profile tanner-test --input-device 1 --qwen-fixed-seed 12345 --tts-response-mode whole --stt-endpoint-final-only --luna-model gpt-6-luna --luna-service-tier default`

### Acceptance sequence

1. Stay silent for 10–15 seconds while Jarvis is sleeping.
   - No hallucinated `Thank you`, `Bye`, or other text should become a user turn.
   - A provisional noise candidate may be logged and rejected; listening must
     continue without reopening/restarting the whole session.

2. Speak quietly but normally:
   `Hey Jarvis, tell me something interesting about space.`
   - It should wake and route the rest of the same sentence.

3. After the answer, ask quietly:
   `Why is that?`
   - It should be recognized even if RMS/peak is low.
   - Jarvis must actually speak the response.

4. Interrupt while Luna/Qwen is still preparing:
   `Actually, tell me about Mars instead.`
   - The old response should cancel only after transcript evidence exists.

5. Interrupt during audible speech:
   `Wait, explain that more simply.`
   - Playback should stop promptly.
   - The full interruption should become the next turn.
   - Interruption context/heard text should remain intact.

6. Remain silent during one full Jarvis answer.
   - Background noise must not fabricate a user turn and trigger a reply loop.

### What to inspect in the console

Healthy behavior should show transcript-confirmed turns and may show rejected
provisional candidates. It should no longer show the old Repair3 pattern where a
short/quiet candidate is rejected only for `speech-span-too-short`,
`insufficient-energy`, or `peak-below-threshold`.
