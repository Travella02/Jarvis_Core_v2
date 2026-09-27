# Testing Guide — 0.0.4 Repair31

Focused:
`python -m unittest tests.unit.test_repair31_qwen_fixed_seed tests.unit.test_repair31_preserves_repair27_voice_path -v`

Full:
`python -m unittest discover -s tests -v`

Run the fixed-seed candidate:
`python -m apps.voice_lab --turns 5 --tts-provider qwen3-streaming --voice-profile tanner-test --input-device 1 --qwen-fixed-seed 12345`

Optional Repair27 control in the same patched tree:
`python -m apps.voice_lab --turns 5 --tts-provider qwen3-streaming --voice-profile tanner-test --input-device 1`

Standard five prompts:
1. Jarvis, tell me something interesting about space.
2. Why does that happen?
3. Explain it more simply.
4. Tell me another interesting fact.
5. Tell me a short joke.

Acceptance:
- no robotic/underwater/runaway audio;
- first sentence sounds closer to later sentences;
- initial response stays Repair27-fast;
- no loss of natural expressiveness.

Sentence pauses and click/pop suppression are intentionally deferred to the next
repair so this A/B isolates voice consistency.
