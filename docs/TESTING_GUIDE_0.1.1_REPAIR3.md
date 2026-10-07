# 0.1.1 Repair3 — Testing Guide

Do not commit until automated and live acceptance pass.

## Focused gate

```powershell
python -m unittest `
  tests.unit.test_0_1_1_repair3_response_budget_persona `
  tests.unit.test_0_1_1_repair2_adaptive_conversational_brevity `
  tests.unit.test_0_1_1_repair1_silent_sleep_brevity `
  tests.unit.test_0_1_1_realtime_sleep_lifecycle `
  tests.integration.test_0_1_1_desktop_presence_lifecycle -v
```

## Full regression

```powershell
python -m unittest discover -s tests -v
python -m core.diagnostics
npm run desktop:check
```

## Live acceptance

1. `Jarvis, tell me something interesting about space.`
2. `Why does that happen?` — must be materially shorter than the previous paragraph behavior.
3. `Give me a detailed explanation of how stars form.` — should use the expanded-response path and remain naturally detailed.
4. `That's all, Jarvis.` — must sleep silently and clear the caption.
5. Wake Jarvis and give one request that requires Core delegation to ensure the 80-token normal ceiling did not break function calling.

Watch the terminal for `[Desktop response budget]` lines. A normal answer may finish naturally below the ceiling or report that the cap was reached; detailed answers should show the larger per-response budget.
