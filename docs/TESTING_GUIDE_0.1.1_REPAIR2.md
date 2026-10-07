# 0.1.1 Repair2 — Testing Guide

Do not commit until automated and live acceptance pass.

## Focused tests

```powershell
python -m unittest `
  tests.unit.test_0_1_1_repair2_adaptive_conversational_brevity `
  tests.unit.test_0_1_1_repair1_silent_sleep_brevity `
  tests.unit.test_0_1_1_realtime_sleep_lifecycle `
  tests.unit.test_0_1_1_desktop_wake_sleep_contract `
  tests.integration.test_0_1_1_desktop_presence_lifecycle -v
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

1. Ask a normal factual question: **“Jarvis, tell me something interesting about space.”**
2. Follow with exactly: **“Why does that happen?”**
   - The follow-up should normally be one or two short sentences and should answer only the missing reason.
   - It should not repeat the full first answer or add multiple analogies/background paragraphs.
3. Ask: **“Give me a detailed explanation of how stars form.”**
   - This should expand naturally and prove explicit detail requests still override the concise default.
4. Say: **“That’s all, Jarvis.”**
   - Sleep must remain silent and the caption must clear.

Personality is not a failure. Natural reactions such as “Good question” are allowed; unnecessary explanation is the failure condition.
