# Testing Guide — 0.0.4 Repair27

Focused:
`python -m unittest tests.unit.test_repair27_fast_first_speech tests.unit.test_voice_chunking tests.integration.test_voice_response_policy -v`

Full:
`python -m unittest discover -s tests -v`

Live:
`python -m apps.voice_lab --turns 5 --tts-provider qwen3-streaming --voice-profile tanner-test --input-device 1`

Prompts:
1. Jarvis, tell me something interesting about space.
2. Why does that happen?
3. Explain it more simply.
4. Tell me another interesting fact.
5. Tell me a short joke.

Compare:
- Luna first text -> first speech chunk
- speech end -> first audible audio
- first chunk words/chars
- perceived naturalness of the opening sentence

Do not commit until the live five-turn test is accepted.
