# Issue 094 — Verify real Core/Luna delegation, authorized speech and cancellation

## Background

Repair13 established fast private PCM, Repair15 accepted natural wake-only acknowledgments. Prior live performance tests had `core_calls=0`; successful direct answers do not demonstrate Core/Luna delegation.

## Risk

Model may select `ask_luna` but no Core call may run; Core might complete but speech not play; interrupted or sleeping session might hear stale Core result; actions might be incorrectly represented as performed.

## Scope / resolution candidate

Add a strictly opt-in 8-second hold mode using the accepted PCM trim, one deterministic backend test suite and read-only observation report. Preserve unmodified everyday mode and existing authority. Validate on Windows with a real provider before marking complete.

## Acceptance evidence

- Selection > Core started > Core finished > spoken current-turn result.
- New utterance and sleep supersede held results with `stale_result_discarded` and no stale audio.
- Actions remain unexecuted. Sleep, wake and interruption safe. Fail closed if logs don't prove a step.

**Status: awaiting Windows live acceptance, do not commit.**
