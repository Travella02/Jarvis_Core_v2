# Jarvis Core v2 0.1.3 Repair16 Repair1 — eight-second audible cancellation cue

**Base required:** installed Repair16 + Diagnostic1 + Diagnostic2 + Diagnostic3, after accepted Repair15 (and rejected/rolled-back Repair14). Keep the accepted Repair13 trimmed PCM path.

## Scope

- **Test mode only** (`mini-overlap-luna-trim-cancel-test`, or its non-trim cancellation counterpart): Core has already completed a private result. The existing 8-second hold remains **8 seconds**.
- At hold start, Core sends a control-only `core_luna_cancel_hold` event. The desktop renderer plays two short local oscillator notes over the normal audio output and shows `TEST MODE · INTERRUPT NOW (8 SEC)` below the orb. No model-generated speech or Core result is released.
- Interruption/new user turn or sleep during the hold invalidates the held Core result synchronously before any voice release. Logs include `phase=stale_result_discarded` and `phase=test_summary | outcome=PASS | result_released=false`.
- If the 8 seconds expire without cancellation, logs say `outcome=NOT_TESTED | reason=hold_expired`. An expired hold is not a passing cancellation test.
- Test-only control events are separate from `core_luna_result`, so regression tests assert only actual Core-answer deliveries. UI notifications cannot authorize speech.
- Missing cue audio falls back to the visible banner and `phase=cue_ack | audio_scheduled=False`; it does not change Core audio policy. The final verdict is from Core invalidation, not whether a sound played.

## Out of scope

- No change to normal `mini-overlap-luna-trim` speed, wake/sleep policy, Realtime Mini model, routing, output-token limits, Luna provider behavior, or actions (still dry-run).
- No forced Core escalation. Ask a question that actually triggers `tool=ask_luna` to perform the hold test.
- No changes to accepted Repair13 PCM trimming or Repair15 wake acknowledgments.

## Verification

Automated tests include the existing cancellation suite (updated to ignore cue control events), new deterministic held-result/new-turn/sleep tests, and static desktop-audio isolation checks.

**Acceptance requires Windows desktop build and actual audible cue test.** Unit tests cannot prove that a user's audio device played a tone. Keep patch/install artifacts and backups until accepted; do not commit yet.
