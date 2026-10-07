# Testing Guide — 0.1.2-repair3

Do not clean patch artifacts or commit until live acceptance passes.

## Automated checks

Run the focused Repair3 gate/bridge tests, then the full suite, diagnostics, and desktop static check.

## Live Test 1 — Core reasoning with zero pre-speech leakage

Say exactly:

`Jarvis, use your Core to explain why idempotency matters when a client reconnects to a runtime.`

Expected:
- Absolutely no “let me think”, “let me pull in Core”, acknowledgement, clipped syllable, or other audio before the useful answer.
- The UI may show THINKING/WORKING while the hidden route/Core work happens.
- The first audible words are the actual idempotency answer.
- No mention of Core/routing/tools/providers in the answer.
- Captions cover the full audible answer and do not disappear early.

## Live Test 2 — Unsupported background task remains fail-closed

Say exactly:

`Jarvis, use your Core to start a background task that builds a project while I’m gone.`

Expected:
- No acknowledgement or claim that the task is starting/queued/prepared.
- One complete answer stating that durable/background build capability is unavailable in this build.
- No contradiction.
- Full caption continuity.

## Live Test 3 — direct-response latency regression

Say exactly:

`Jarvis, what planet is known as the Red Planet?`

Expected:
- One direct answer: Mars.
- No routing/Core/tool narration and no “let me think” filler.
- No noticeable long silent stall. Record the approximate perceived delay if it feels materially slower than pre-Repair3 direct conversation.

## Live Test 4 — sleep regression

Say exactly:

`That’s all, Jarvis.`

Expected:
- Jarvis returns to sleeping presence without speaking an extra acknowledgement.
- Local wake remains available.
