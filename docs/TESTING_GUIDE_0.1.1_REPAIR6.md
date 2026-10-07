# 0.1.1 Repair6 — Testing Guide

Do not clean patch artifacts or commit until live acceptance passes.

## Focused gate

```powershell
python -m unittest `
  tests.unit.test_0_1_1_repair6_sleep_transcript_surface `
  tests.unit.test_0_1_1_repair5_manual_response_policy `
  tests.unit.test_0_1_1_repair4_audio_safe_budget `
  tests.unit.test_0_1_1_repair1_silent_sleep_brevity `
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

1. Wake Jarvis and ask: **“Jarvis, tell me something interesting about space.”**
2. Say: **“Why does that happen?”** Confirm the compact response behavior from Repair5 remains intact.
3. Say: **“Give me a detailed explanation of how stars form.”** Confirm:
   - the orb remains in exactly the same vertical position,
   - the caption viewport stays the same height,
   - old lines fade away at the top while the newest lines remain visible,
   - the expand control opens a full-screen readable transcript and Escape closes it.
4. Say: **“That’s all, Jarvis.”** Confirm Jarvis produces no spoken sign-off, immediately enters SLEEPING, and clears the caption/expanded transcript.
5. Leave Jarvis awake for 60+ seconds once more and confirm idle sleep still works.
