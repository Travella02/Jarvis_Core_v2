# 0.0.9 Repair6 Testing Guide

## Focused tests

```powershell
python -m unittest `
  tests.unit.test_0_0_9_repair6_realtime_default `
  tests.unit.test_0_0_9_repair4_realtime_contract `
  tests.unit.test_0_0_9_repair4_webrtc_lifecycle `
  tests.integration.test_0_0_9_repair5_realtime_multipart_form `
  tests.integration.test_0_0_9_repair4_realtime_core_delegation `
  tests.integration.test_conversation_core -v
```

## Full regression

```powershell
python -m unittest discover -s tests -v
```

## Diagnostics

```powershell
python -m core.diagnostics
```

## Live default five-turn acceptance

```powershell
python -m apps.gpt_realtime_webrtc_lab --turns 5 --voice cedar
```

Say exactly:

1. `Jarvis, tell me something interesting about space.`
2. `Why does that happen?`
3. `Explain it more simply.`
4. While Jarvis is still speaking #3: `Tell me another interesting fact.`
5. `Tell me a short joke.`

Confirm natural audio, clean interruption, no clipping of the last sentence, five captured user turns, and `Status: ok`.

## Core delegation acceptance

Run the same command and say exactly:

1. `Jarvis, use your Core to explain why idempotency matters when a client reconnects to a runtime.`
2. `Now give me that same answer in one sentence.`
3. `Use your Core to compare two architecture options for Jarvis and explain the tradeoffs.`
4. While Core is working or Jarvis is beginning the answer: `Actually, keep it to three short points.`
5. `Based on that, which direction would you choose?`

Confirm at least one Core delegation, natural continuation after the function result, interruption/correction remains usable, and `Status: ok`.
