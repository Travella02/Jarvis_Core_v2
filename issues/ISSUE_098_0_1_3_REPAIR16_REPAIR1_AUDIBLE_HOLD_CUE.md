# ISSUE 098 — cancellation test difficult to time by reading terminal

**Observed:** user couldn't reliably see `phase=holding_result` in scrolling terminal and interrupt within eight seconds. Core cancellation was not reliably validated under human timing, despite correct automatic cancellation logic.

**Fix candidate:** send test-only `core_luna_cancel_hold` WebSocket control event at the start of the existing eight-second hold. Desktop plays a short audible notification and displays a temporary hold indicator. Add unique test-result log markers and deterministic cancellation tests. Keep normal mode and Core authority unchanged.

**Acceptance:** audible cue on Windows audio output, new-question interruption and sleep before hold expires, no stale Core voice, normal trimmed-PCM unaffected, full regression passes. No production commitment until live acceptance.
