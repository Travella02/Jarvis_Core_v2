# Jarvis Core v2 — 0.1.3 Repair16: Core/Luna and interruption live acceptance

## Scope / non-negotiables

This is a **validation patch**, not a new routing algorithm. It adds a trimmed-PCM Core cancellation-test launcher, deterministic tests, and a read-only, transcript-free report. Regular `mini-overlap-luna-trim` is behavior-identical to accepted Repair15 (no 8-second hold). External computer actions are still **dry-run**. No Decisions shadow and no rejected compact router.

### Automated checks (run one by one in activated `.venv`)

```powershell
python -m unittest tests.unit.test_0_1_3_repair16_delegation_acceptance -v
```
```powershell
python -m unittest discover -s tests -v
```
```powershell
python -m core.diagnostics
```
```powershell
npm run desktop:check
```
```powershell
npm run desktop:build
```

### Live A — normal, fast trimmed-PCM mode

Close all existing Jarvis/Electron sessions. Run:

```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim
```

1. Say **`Hey Jarvis.`** and verify he responds briefly.
2. Ask **`What is seventeen times six?`**. He must answer 102 without a long Core response. Check no clipping, latency similar to Repair13/15.
3. Say **`Jarvis, please ask Core/Luna to analyze a multi-tenant assistant architecture with tenant isolation, authorization boundaries, retries, and audit logging; compare the risks of three designs.`** (intentional explicit delegation test). We need `tool=ask_luna`, `queued=True`, `phase=core_started`, `phase=result | status=completed`, `phase=started` under `[Jarvis Luna Voice]`, `phase=synthesis_completed` for the same turn, and a correct spoken answer. *If Mini answers directly, delegation was not validated; don't mark a pass.*
4. Ask naturally without naming Core: **`Compare event sourcing, transactional outboxes, and distributed locks for avoiding duplicate payments under retries and service crashes; include failure cases.`** Check if Mini independently escalates. A direct answer is a classification observation, not proof that the Core bridge is broken.
5. Ask **`Jarvis, create a file on my desktop called repair16-probe.txt.`** This **must NOT** create any file: actions are dry-run. Confirm Jarvis does not falsely claim it executed an action. `test_action` may be selected but must be `dry_run=True, executed=False`.
6. Say **`Thanks, Jarvis.`** He should stay awake. Then **`Thanks Jarvis, that's all.`** He should sleep without speech.

**Report real Core usage only if** `core_started` and Core result are logged for the same request. `tool=ask_luna` alone is *not* a successful delegation. A completed Core text result is not proof the voice was audibly delivered, so listen and verify.

### Live B — deterministic cancellation window, *separate opt-in mode*

Close Jarvis fully. Run:

```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim-cancel-test
```

Confirm banner has `pcm_trim=on | cancellation_test=on | core_luna=on`. This mode **intentionally holds completed Core answers 8 seconds**; do not assess its speed against baseline. It does not change normal launch behavior.

1. Ask the explicit complex architecture question from Live A. Wait until the console prints `[Jarvis Luna Cancel Test] ... phase=holding_result`. During those 8 seconds, say **`Actually, change that. What's nine times eight?`**. Jarvis should answer 72, and no earlier Core reply should play. Look for `phase=stale_result_discarded | voice_delivered=false`.
2. Ask the complex Core question again; when `phase=holding_result` appears, say **`That's all, Jarvis.`**. He should go to sleep. The previous Core result must not play, even after waiting over 8 seconds. Look for `phase=stale_result_discarded` and `phase=sleep`.
3. Wake Jarvis and ask **`Jarvis, what's the capital of France?`**. He should answer Paris correctly without waiting eight seconds (direct path unaffected).

If your complex prompt does not trigger `ask_luna`, you cannot perform the hold test yet. Record that routing issue; **do not** simulate success.

### Five standard wake/sleep regression phrases

1. **`Hey Jarvis, what planet is called the Red Planet?`** — wake, answer Mars directly.
2. **`Go to sleep, Jarvis.`** — sleep silently.
3. **`Jarvis, what's seventeen times six?`** — wake and answer 102.
4. **`Thanks, Jarvis.`** — normal gratitude, remain awake.
5. **`Thanks Jarvis, that's all.`** — silent sleep.

Also test wake-only **`Jarvis.`**, wake-only **`Hey Jarvis.`**, and conversational interruption while Jarvis is speaking. Watch for clipping, popping, repeated responses, stale Core text, and `sleep_evidence_mismatch` when STT mishears a phrase. Do not change wake-matching policy in this repair.

### Optional read-only log summary

If you saved the terminal log as `repair16_live.log`, run:

```powershell
python .\scripts\repair16_delegation_report.py .\repair16_live.log
```

The report counts route selections, Core executions/results, voice synthesis completion, dry-run action selections, hold cancellations, and verified sleeps; it never outputs transcripts. It **cannot confirm audible playback** or true routing correctness by itself. Share screenshots or summary, not API keys. `*.log` files are ignored by Git.

### Acceptance criteria

- Explicit request actually reaches **Core**, returns a real answer, and is spoken correctly (unless a genuine provider error is documented).
- Mini handles simple questions with fast Repair13 PCM trim and intact sound.
- No external actions performed or falsely claimed.
- Late Core answer never speaks after new turn/sleep in hold test; no double replies.
- Five standard wake/sleep regression phrases work.
- Automated tests, diagnostics and Windows build pass.

Retain patch files, installer and `.patch_backups` until live user acceptance; **do not commit yet**. After review, decide whether to release 0.1.3 or keep repairing. The hold test is intentionally opt-in and must not become the default.
