# 0.1.1 Repair7 — Testing Guide

Do not commit until automated and live acceptance pass.

## Focused tests

```powershell
python -m unittest `
  tests.unit.test_0_1_1_repair7_single_pass_detail_scroll `
  tests.unit.test_0_1_1_repair6_sleep_transcript_surface `
  tests.unit.test_0_1_1_repair5_manual_response_policy `
  tests.unit.test_0_1_1_repair1_silent_sleep_brevity `
  tests.integration.test_0_1_1_desktop_presence_lifecycle -v
```

## Full regression / diagnostics

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

1. Wake Jarvis and say **“Give me a detailed explanation of how stars form.”**
   - Jarvis may use one brief natural lead-in, but must not say a waiting acknowledgement such as “let me think for a second” and then restart with another acknowledgement.
   - The detailed answer should be one continuous response.
2. While the response is still typing, scroll the inline text upward.
   - The orb and input must not move.
   - The viewport must stay where you put it rather than snapping back to the bottom on every new character.
   - Scroll back near the bottom; automatic following should resume.
3. Use the expand button and confirm the full response reader is still independently scrollable and closes normally.
4. Ask **“Why does that happen?”** after a normal answer and confirm the compact response behavior still works.
5. Say **“That’s all, Jarvis.”** and confirm silent sleep still works.

Do not clean patch/apply artifacts until this live gate passes.
