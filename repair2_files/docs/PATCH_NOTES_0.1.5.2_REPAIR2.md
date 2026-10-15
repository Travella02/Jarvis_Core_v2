# Jarvis Core v2 0.1.5.2 Repair2 — Action Settlement and Conversational Lead-in

## Baseline
Only install after **0.1.5.2 Repair1** on an otherwise unchanged source tree. The installer checks source SHA-256 after CRLF normalization and the Repair1 test anchor before changing files. Does not modify accepted 0.1.4 audio, wake/sleep, VAD, routing, Luna or PCM trim.

## What changed
- Extend independent Core approval for explicit standalone commands like `Go ahead and open YouTube`, `Hey go ahead and open YouTube`, `Jarvis, go ahead and open YouTube for me`, `Could you go ahead and open YouTube?`. This does not approve arbitrary URLs, Google, negated, conditional, compound or quoted commands.
- Core action result now has a same-turn/epoch acknowledgment owner independent of transient router completion. Only an exact, current action can update the interface.
- If the Core response is not delivered within 5 seconds, Jarvis returns to Ready and displays an **uncertain** result. It never reissues a browser launch or falsely claims that nothing opened.
- After an on-time successful or failed result, Jarvis goes back to Ready; a short same-turn Ready reassertion handles late cancelled candidate events. It never changes the state of a newer turn.
- Host logs `[Jarvis Action UI] turn=...` for completed/failed/timeout browser action feedback, to diagnose future UI issues.
- Successful visible browser actions remain silent. Failed action explanation is in text only pending a later scoped enhancement.

## Live acceptance
Must still verify on Windows. Do not clean, commit, or call 0.1.5.2 accepted until verified. See `docs/TESTING_GUIDE_0.1.5.2_REPAIR2.md`.
