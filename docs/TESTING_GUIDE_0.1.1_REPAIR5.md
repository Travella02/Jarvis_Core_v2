# 0.1.1 Repair5 — Testing Guide

Do not commit until automated and live acceptance both pass.

## Focused tests

```powershell
python -m unittest `
  tests.unit.test_0_1_1_repair5_manual_response_policy `
  tests.unit.test_0_1_1_repair4_audio_safe_budget `
  tests.unit.test_0_1_1_repair3_response_budget_persona `
  tests.unit.test_0_1_1_repair2_adaptive_conversational_brevity `
  tests.unit.test_0_1_1_repair1_silent_sleep_brevity -v
```

Expected: 21 tests, OK.

## Full regression and diagnostics

```powershell
python -m unittest discover -s tests -v
python -m core.diagnostics
npm run desktop:check
```

Expected: 468 tests, same existing skip, `Status: ok`.

## Live acceptance

```powershell
npm run desktop
```

Say exactly:

1. **“Jarvis, tell me something interesting about space.”**
2. **“Why does that happen?”**
3. **“Give me a detailed explanation of how stars form.”**
4. **“That’s all, Jarvis.”**

Confirm:

- #1 and #2 finish naturally rather than being cut off.
- #1 and #2 are materially shorter than the earlier paragraph-length answers; target shape is one or two compact sentences.
- #3 takes the expanded path and is allowed to be longer.
- sleep remains silent and clears the caption.
- Terminal `Desktop response budget` lines should normally end with `status=completed`, not `reason=max_output_tokens`.
- Response latency should remain close to the prior desktop baseline; manual response creation is sent immediately on Semantic VAD `speech_stopped` and does not add a second model call.

If ordinary answers are still too verbose but complete, do not lower the token ceiling again. Adjust the response-specific conversational policy instead.
