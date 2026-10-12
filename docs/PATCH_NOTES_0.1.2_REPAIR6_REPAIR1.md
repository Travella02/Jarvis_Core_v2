# 0.1.2 Repair6-Repair1 — Portable, deterministic shadow-probe tests

**Scope:** Only Repair6's test suite and accompanying documentation/metadata are updated. The existing Realtime gate, voice, Core bridge, speculative probe runtime, and authorization rules are unchanged.

## Live failure reproduced

1. `Path(...).read_text()` without an encoding used the Windows `cp1252` default and failed when reading a UTF-8 `App.tsx` byte sequence (`UnicodeDecodeError` near offset 28683).
2. A test assumed `asyncio.sleep(0.015)` guaranteed that a no-delay async model stream had completed. On Windows the test could close the probe first; the probe correctly logged `status=cancelled`, but the test expected `status=completed`.

## Correction

- Read the TypeScript source using `encoding="utf-8"`, independent of the operating-system code page.
- Await actual async task completion for the completed-result and timeout tests, with a 3-second safety timeout.
- Use an explicit `asyncio.Event` signaling provider entry before routing/new-turn cancellations. This removes fragile event-loop scheduling assumptions from the remaining concurrency tests.
- Retain all nine assertions and all production shadow-probe behaviors. Canceled work stays canceled and is never published to UI/audio.

## Verification

- Focused: nine tests pass.
- Full suite: 536 run, one pre-existing skip.
- No live audio behavior or routing modifications; the original Repair6 live tests are unchanged and still required before acceptance.

Do not clean up artifacts or commit until user validates Repair6 live behavior.
