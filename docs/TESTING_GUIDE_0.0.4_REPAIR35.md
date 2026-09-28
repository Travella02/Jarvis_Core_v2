# Testing Guide — 0.0.4 Repair35

Focused:
`python -m unittest tests.unit.test_repair35_luna_path_diagnostics tests.integration.test_repair35_openai_diagnostics -v`

Full:
`python -m unittest discover -s tests -v`

First isolate Luna only.

Standard/auto:
`python -m apps.luna_latency_probe --rounds 5 --transport websocket --service-tier auto`

Fast A/B:
`python -m apps.luna_latency_probe --rounds 5 --transport websocket --service-tier fast`

Compare:
- raw Luna TTFT average
- Conversation Core TTFT average
- continuation on Core round 2+
- actual service tier

If Fast mode materially wins, live candidate:
`python -m apps.voice_lab --turns 5 --tts-provider qwen3-streaming --voice-profile tanner-test --input-device 1 --qwen-fixed-seed 12345 --tts-response-mode whole --stt-endpoint-final-only --luna-service-tier fast`

Standard five live prompts:
1. Jarvis, tell me something interesting about space.
2. Why does that happen?
3. Explain it more simply.
4. Tell me another interesting fact.
5. Tell me a short joke.

Do not accept Fast mode unless the `actual_tier` confirms Fast/Priority
processing and the improvement is worth the per-token premium.
