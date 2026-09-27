# Testing Guide — 0.0.4 Repair33

Focused:
`python -m unittest tests.integration.test_repair33_whole_response_tts tests.unit.test_repair33_preserves_human_response_policy -v`

Full:
`python -m unittest discover -s tests -v`

Whole-response candidate:
`python -m apps.voice_lab --turns 5 --tts-provider qwen3-streaming --voice-profile tanner-test --input-device 1 --qwen-fixed-seed 12345 --tts-response-mode whole`

Repair31 control, available without rollback:
`python -m apps.voice_lab --turns 5 --tts-provider qwen3-streaming --voice-profile tanner-test --input-device 1 --qwen-fixed-seed 12345 --tts-response-mode streaming`

Standard five prompts:
1. Jarvis, tell me something interesting about space.
2. Why does that happen?
3. Explain it more simply.
4. Tell me another interesting fact.
5. Tell me a short joke.

Listen for:
- one consistent voice across the complete answer;
- natural period/question/comma prosody produced by Qwen itself;
- no sentence-boundary voice reset;
- preserved humor/personality;
- whether first response still feels immediate.

Compare:
- Luna first text -> Luna response complete
- Luna response complete -> TTS request
- TTS request -> first waveform
- speech end -> first audible audio

Do not commit until the live whole-response test is accepted.
