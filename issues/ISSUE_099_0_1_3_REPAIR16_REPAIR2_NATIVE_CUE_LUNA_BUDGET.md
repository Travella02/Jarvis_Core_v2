# Issue 099 — Repair16 Repair2: inaudible hold cue and Luna budget exhaustion

## Reproduced facts
- In the live Repair16 Repair1 test, terminal showed `phase=holding_result` and expired `outcome=NOT_TESTED` while the user reported **no audible cue**. Browser-created `AudioContext` resumed from a WebSocket callback was not a reliable notification path.
- The provider returned `response_status=incomplete`, `incomplete_reason=max_output_tokens`, `output_tokens=256`, `output_limit=256` during a complex delegated task.

## Resolution to test
- On Windows, an in-memory two-note PCM WAV is played on the default wave output via `winsound.PlaySound` in a worker thread. The eight-second hold begins after native cue completion. The banner remains visible; browser cue is fallback on Windows failure.
- Desktop Core/Luna output budget is at least 1024 by default, even with an inherited 256 generic provider limit; explicit `JARVIS_DESKTOP_LUNA_VOICE_MAX_OUTPUT_TOKENS` may override.
- Test-only changes do not alter Core action authority, wake/sleep, ordinary Mini, or PCM trimming.

## Acceptance
- User hears the standalone native cue in their selected Windows default headphones.
- Core provider records the increased limit on live delegation and completes the selected complex request.
- Before-playback cancellation by interruption or sleep yields `outcome=PASS` and never releases a stale answer.
- All regression suites, diagnostics and Windows production build pass.
