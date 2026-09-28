# Testing Guide — 0.0.4 Repair34

Focused:
`python -m unittest tests.unit.test_repair34_whisper_endpoint_final_only tests.unit.test_repair34_preserves_whole_response_voice -v`

Full:
`python -m unittest discover -s tests -v`

Candidate:
`python -m apps.voice_lab --turns 5 --tts-provider qwen3-streaming --voice-profile tanner-test --input-device 1 --qwen-fixed-seed 12345 --tts-response-mode whole --stt-endpoint-final-only`

Optional Repair33 control in the same patched tree:
`python -m apps.voice_lab --turns 5 --tts-provider qwen3-streaming --voice-profile tanner-test --input-device 1 --qwen-fixed-seed 12345 --tts-response-mode whole`

Standard five prompts:
1. Jarvis, tell me something interesting about space.
2. Why does that happen?
3. Explain it more simply.
4. Tell me another interesting fact.
5. Tell me a short joke.

Compare primarily:
- endpoint -> STT final
- transcript accuracy
- speech end -> first audible audio

Natural whole-response delivery should remain identical because Repair34 does not
modify TTS scheduling or response policy.
