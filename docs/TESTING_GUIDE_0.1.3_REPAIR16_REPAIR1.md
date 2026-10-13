# 0.1.3 Repair16 Repair1 — live acceptance checklist

The 8-second window is **unchanged**. Do not watch the terminal while trying to respond: **listen for a two-note ding, then immediately speak.** Only the opt-in cancellation-test launch plays the ding.

## Automated verification (one command at a time)

```powershell
python -m unittest tests.unit.test_0_1_3_repair16_repair1_cue -v
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

## Live A — Core interruption

1. Close all Jarvis desktop windows. Start:

```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim-cancel-test
```

2. Wake Jarvis: "Hey Jarvis." If the wake-only greeting completes, ask: **"Jarvis, compare three production architectures for a multi-tenant assistant, with tenant isolation, authorization, retries, and audit logging. Which would you choose?"**
3. If Mini does not select `ask_luna`, this attempt isn't a cancellation test—try a sufficiently complex request again and report the routing issue.
4. When you hear the **two-note chime** and see `TEST MODE · INTERRUPT NOW (8 SEC)`, promptly say: **"Actually, forget that. What's nine times eight?"**
5. Jarvis should answer **72**; the previous Core architecture explanation must **never** start. Core should log `phase=stale_result_discarded`, followed by `phase=test_summary | outcome=PASS | reason=new_turn` (or `sleep_or_cancel` if the client used its cancellation path).

## Live B — sleep cancels Core

Keep the same test mode running. Ask the complex architecture question again. On the **ding**, say **"That's all, Jarvis."** Jarvis must sleep and never play the old answer. Core must report `phase=test_summary | outcome=PASS`, and the sleep path should also verify its own lifecycle command.

If it says `outcome=NOT_TESTED | reason=hold_expired`, your interruption came after eight seconds or was not received. That is **not** a safety failure, but it does **not** establish a passing cancellation test.

If you do not hear the ding, check Windows output volume and the `phase=cue_ack | audio_scheduled=` line. The on-screen banner provides a backup, but don't grade an inaudible-cue attempt as successfully meeting the audible-cue goal.

## Normal-mode control

Close the test window. Run:

```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim
```

Ask "What's nine times eight?" and verify that Jarvis answers quickly, with no cue or artificial 8-second wait. No audio popping, clipping, or silent lead-in should return.

## Five standard wake/sleep checks

1. "Hey Jarvis, what planet is called the Red Planet?" — Mars
2. "Go to sleep, Jarvis." — sleeps silently
3. "Jarvis, what's seventeen times six?" — 102
4. "Thanks, Jarvis." — stays awake
5. "Thanks Jarvis, that's all." — sleeps silently

Report the audible cue, wake/sleep behavior, and PASS/NOT_TESTED lines. Don't clean/commit until accepted. Identity style, delegation consistency, and Mini output-length policy are separate follow-ups.
