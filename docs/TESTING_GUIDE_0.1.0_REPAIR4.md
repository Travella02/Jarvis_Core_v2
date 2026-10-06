# 0.1.0 Repair4 — Testing Guide

Do not commit until automated and live acceptance both pass.

## 1. Focused tests

```powershell
python -m unittest `
  tests.unit.test_0_1_0_repair4_playback_responsive `
  tests.unit.test_0_1_0_repair3_orb_state_transitions `
  tests.unit.test_0_1_0_repair2_desktop_presence `
  tests.unit.test_0_1_0_repair1_desktop_polish `
  tests.integration.test_0_1_0_repair1_desktop_routing `
  tests.unit.test_0_1_0_desktop_contract `
  tests.integration.test_0_1_0_desktop_host -v
```

Expected: `Ran 44 tests` and `OK`.

## 2. Desktop syntax/security check

```powershell
npm run desktop:check
```

## 3. Full regression

```powershell
python -m unittest discover -s tests -v
```

Expected: `Ran 429 tests` and `OK` with the same one existing skip.

## 4. Diagnostics

```powershell
python -m core.diagnostics
```

Expected final line: `Status: ok`.

## 5. Launch

```powershell
npm run desktop
```

## 6. Exact live playback-state test

Say:

1. **“Jarvis, tell me something interesting about space.”**
2. **“Explain that in a little more detail.”**
3. **“Now tell me a short joke.”**

Confirm:

- Jarvis enters `SPEAKING` when Cedar audio starts.
- The orb remains in its speaking look through the final audible word.
- Only after Cedar is actually finished does the orb smoothly return toward `READY`.
- The caption remains character-paced and the full final text is visible when playback finishes.

## 7. Interruption test

While Jarvis is speaking, say:

**“Actually, tell me something else.”**

Confirm the audible response stops, the orb blends into `LISTENING`, and an `output_audio_buffer.cleared` event does not snap the UI back to `READY` over the newer state.

## 8. Responsive layout test

With Jarvis idle:

1. Restore the app to a smaller window.
2. Maximize/fullscreen it.
3. If available, move it to another monitor with a different resolution or Windows scale setting.

Confirm the entire presence grows/shrinks together: orb, JARVIS label, state label, transcript, input, and spacing. The orb should occupy roughly the same percentage of the smaller viewport dimension rather than remaining a fixed pixel size.

## 9. Cleanup

Only after live acceptance: remove apply/patch/backup artifacts, rerun the full regression, inspect Git, then commit.
