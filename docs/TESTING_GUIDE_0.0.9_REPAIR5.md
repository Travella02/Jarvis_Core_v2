# 0.0.9 Repair5 Testing Guide

## 1. Focused tests

```powershell
python -m unittest `
  tests.integration.test_0_0_9_repair5_realtime_multipart_form `
  tests.integration.test_0_0_9_repair4_realtime_webrtc_creation `
  tests.integration.test_0_0_9_repair4_realtime_core_delegation `
  tests.unit.test_0_0_9_repair4_realtime_contract `
  tests.unit.test_0_0_9_repair4_webrtc_lifecycle -v
```

Expected: all tests pass.

## 2. Full regression

```powershell
python -m unittest discover -s tests -v
```

Expected candidate count after Repair5: 379 tests, with the pre-existing single skip.

## 3. Live Realtime WebRTC A/B test

```powershell
python -m apps.gpt_realtime_webrtc_lab --turns 5 --voice cedar --realtime-model gpt-realtime-2.1 --reasoning-effort low
```

Say exactly:
1. `Jarvis, tell me something interesting about space.`
2. `Why does that happen?`
3. `Explain it more simply.`
4. While Jarvis is still answering #3: `Tell me another interesting fact.`
5. `Tell me a short joke.`

Acceptance focus:
- WebRTC session creation succeeds instead of HTTP 400.
- Ordinary general-knowledge turns are answered directly by Realtime when appropriate.
- Interruption is natural.
- Audio remains clean over browser WebRTC.
- No project API key is exposed to the browser.
- Jarvis Core delegation remains available for requests that need memory, private state, tools, actions, or deeper backend work.
