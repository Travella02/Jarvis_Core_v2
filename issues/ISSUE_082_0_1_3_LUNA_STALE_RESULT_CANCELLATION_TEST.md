# ISSUE 082 — Luna cancellation race still lacks deterministic live proof

## Observation
In a voice interruption test, Mini cancelled the speculative first turn and
answered the second question, but the original `ask_luna` tool decision reached
the host only after a new user turn. No Core Luna execution was observed, so
actual in-flight Core cancellation and late-result suppression remained unproven.

## Repair5 scope
* Add opt-in `mini-overlap-luna-cancel-test` launch mode. It runs the same Core
  reasoning path, but after Luna actually completes, holds the verified answer
  **privately** for eight seconds before notifying Realtime. The hold delays only
  this one test mode; normal `mini-overlap-luna` remains zero hold.
* Log `phase=core_started`, `phase=holding_result`, `phase=stale_result_discarded`
  and `phase=releasing_current_result` to establish which race was exercised.
* Use the existing current-turn and sleep invalidation to suppress stale Core
  output, not new audio, permission, or model routing paths.
* Bound the configuration, preserve dry-run actions and no-external-effects
  invariants, and reject enabling the test hold outside Core Luna probe.

## Live validation
1. Launch cancel-test mode. Ask a Luna-level architecture request. Wait for
   `[Jarvis Luna Cancel Test] phase=holding_result`, then ask another simple
   question before the eight-second hold expires. New response must arrive;
   after eight seconds, see `stale_result_discarded` for old turn and no stale
   voice/captions.
2. Repeat, but during hold say `That's all, Jarvis.` Sleep must complete and
   stale result must not speak after the hold.
3. Restart normal `mini-overlap-luna` (no test hold) and verify one normal Core
   response has ordinary latency; ensure no `holding_result` log.

This test validates late-result quarantine **after Core completed**, not the
cancellation of an HTTP request mid-flight. Separate async unit tests cover
cooperative `cancel_active_turn` when a provider is still executing. Do not
label live in-flight provider cancellation proven solely by a held-result run.

No changes to natural voice, PCM, release/response-length behavior, Decisions
shadow, sleep phrases, user settings or actual computer-action permissions.
