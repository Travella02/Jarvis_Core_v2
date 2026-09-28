# Testing Guide — 0.0.4 Repair36

Focused:
`python -m unittest tests.unit.test_repair36_luna_model_control tests.integration.test_repair36_core_websocket_continuation -v`

Full:
`python -m unittest discover -s tests -v`

## GPT-5.6 Luna control — Standard pricing
`python -m apps.luna_latency_probe --rounds 5 --transport websocket --service-tier default --model gpt-5.6-luna`

## GPT-6 Luna candidate — Standard pricing
`python -m apps.luna_latency_probe --rounds 5 --transport websocket --service-tier default --model gpt-6-luna`

Expected Conversation Core continuation:
- round 1: `continuation=no reason=no_lane lane_committed=yes`
- round 2+: `continuation=yes reason=exact_chain lane_committed=yes`

Compare warm-round TTFT and total latency. Do not use Fast mode for this A/B.

If GPT-6 Luna is acceptable, live candidate:
`python -m apps.voice_lab --turns 5 --tts-provider qwen3-streaming --voice-profile tanner-test --input-device 1 --qwen-fixed-seed 12345 --tts-response-mode whole --stt-endpoint-final-only --luna-model gpt-6-luna --luna-service-tier default`

Standard five prompts:
1. Jarvis, tell me something interesting about space.
2. Why does that happen?
3. Explain it more simply.
4. Tell me another interesting fact.
5. Tell me a short joke.

Do not commit until both model quality and live latency are accepted.
