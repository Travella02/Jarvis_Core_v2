# 0.1.1 Repair4 — Testing Guide

Do not commit until automated and live acceptance pass.

## Focused

```powershell
python -m unittest `
  tests.unit.test_0_1_1_repair4_audio_safe_budget `
  tests.unit.test_0_1_1_repair3_response_budget_persona `
  tests.unit.test_0_1_1_repair2_adaptive_conversational_brevity `
  tests.unit.test_0_1_1_repair1_silent_sleep_brevity -v
```

## Full

```powershell
python -m unittest discover -s tests -v
python -m core.diagnostics
npm run desktop:check
```

## Live
1. `Jarvis, tell me something interesting about space.`
2. `Why does that happen?` — should be concise but complete, not clipped.
3. `Give me a detailed explanation of how stars form.` — should expand naturally.
4. `That's all, Jarvis.` — silent sleep.

Inspect `[Desktop response budget]` lines. Normal responses should report `max_output_tokens=320`; expanded responses should report `1024`. No normal response should end with `reason=max_output_tokens` during the acceptance conversation.
