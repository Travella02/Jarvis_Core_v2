# 0.1.1 Repair1 — Silent Sleep + Conversational Brevity Testing Guide

Do not commit until automated and live acceptance both pass.

## Focused tests

```powershell
python -m unittest `
  tests.unit.test_0_1_1_repair1_silent_sleep_brevity `
  tests.unit.test_0_1_1_realtime_sleep_lifecycle `
  tests.unit.test_0_1_1_desktop_wake_sleep_contract `
  tests.integration.test_0_1_1_desktop_presence_lifecycle `
  tests.unit.test_0_1_0_repair4_playback_responsive -v
```

## Full regression

```powershell
python -m unittest discover -s tests -v
python -m core.diagnostics
npm run desktop:check
```

## Live acceptance

Launch:

```powershell
npm run desktop
```

Then test:

1. Wake with: **“Jarvis, tell me something interesting about space.”**
2. Follow with: **“Why does that happen?”**
   - Jarvis should keep his natural personality, but the answer should normally be a short conversational response rather than a large paragraph.
3. Say: **“That’s all, Jarvis.”** while Jarvis is idle.
   - No spoken acknowledgement should leak through.
   - Audio should stop immediately if any output had begun.
   - The previous caption should disappear as soon as sleep begins.
4. Wake again and, while Jarvis is speaking, say: **“That’s all, Jarvis.”**
   - Existing speech must stop promptly and no new acknowledgement should play before sleep.
5. Wake and ask: **“Give me a detailed explanation of why stars form.”**
   - Jarvis is allowed to be longer because the user explicitly asked for detail.

Confirm sleep still closes Realtime and restores the local wake listener.
