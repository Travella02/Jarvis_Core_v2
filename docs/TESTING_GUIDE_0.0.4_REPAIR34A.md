# Testing Guide — 0.0.4 Repair34a

Focused wiring regression:
`python -m unittest tests.unit.test_repair34a_whisper_flag_wiring tests.unit.test_repair34_whisper_endpoint_final_only tests.unit.test_repair34_preserves_whole_response_voice -v`

Full:
`python -m unittest discover -s tests -v`

Live candidate:
`python -m apps.voice_lab --turns 5 --tts-provider qwen3-streaming --voice-profile tanner-test --input-device 1 --qwen-fixed-seed 12345 --tts-response-mode whole --stt-endpoint-final-only`

Standard five prompts:
1. Jarvis, tell me something interesting about space.
2. Why does that happen?
3. Explain it more simply.
4. Tell me another interesting fact.
5. Tell me a short joke.

Before speaking, verify:
`Whisper endpoint mode: final-only after endpoint`

During the five turns, `stt_first_partial` should be absent. Compare:
- endpoint -> STT final
- transcript accuracy
- speech end -> first audible audio
