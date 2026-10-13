# 0.1.3 Repair16 Repair2 — Windows unittest cue isolation

The Repair2 native Windows cue was audible, but four older asyncio test cases use artificial 70–90 ms hold windows. On Windows those tests accidentally played the actual ~0.6 second WAV, exceeding their 0.35–0.4 second polling deadlines and reporting `Core task did not settle` / `Luna task did not finish`.

This patch changes **only the two existing test files** to patch `apps.desktop_luna.play_native_hold_cue` in their async setup and restore it after each test. No changes to production Core/Luna cancellation behavior, audio cue, eight-second live hold, output budget, or voice pipeline. The tests still exercise the real held-result cancellation logic and assertions. The existing Repair2 cue-specific suite continues to test native WAV generation, simulated Windows playback, failure fallback, and result safety.

Validation locally:
- 30 focused tests passed.
- 8 old cancellation scenarios passed with Windows behavior simulated.
- Full 779-test Python suite passed, 1 skipped in this environment.
- Windows full suite still needs live validation. Do not commit until it passes and subsequent live acceptance completes.
