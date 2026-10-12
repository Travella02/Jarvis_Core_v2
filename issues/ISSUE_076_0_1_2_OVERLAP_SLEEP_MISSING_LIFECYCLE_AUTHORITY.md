# ISSUE-076 — Parallel streaming did not recognize sleep requests

## Symptom
After Repair14 restored local voice wake, "Go to sleep, Jarvis" produced a normal conversational answer and left Realtime active.

## Root cause
Overlap inference exposed only the `ask_luna` and `test_action` dry-run function tools. The `sleep_jarvis` lifecycle capability was absent from its decision schema. The direct candidate was then authorized to speak instead of entering the existing local sleep lifecycle.

## Repair15
- Introduce `sleep_jarvis` as an overlap-only lifecycle function with required user-closing evidence.
- Do not add it to the normal text-only tool probe or real action executor.
- Treat accepted sleep as a real, silent local lifecycle command, **not** a dry-run action.
- Abort speculative audio, clear captions, end the paid session, and restart the existing local Whisper wake listener through `enterSleep()`.
- Reject missing or malformed sleep evidence and ambiguous multiple calls, leaving Jarvis awake.
- Keep current turn binding, PCM audio, normal conversation routing, and Whisper startup logic unchanged.

## Historical comparison
V1 `ISSUE_021` discussed sleep without full provider transcription; `ISSUE_113` and `ISSUE_047` documented premature/stray sleep acknowledgments. This experiment keeps the silent close boundary and avoids adding another generated signoff.

## Live acceptance
1. Wake with voice and immediately say a normal fact question; answer only once.
2. Say `Go to sleep, Jarvis` while awake; the UI must sleep **silently** and local wake listener restart.
3. Say `Jarvis` to wake by voice again.
4. Say `Thanks, Jarvis` (without dismissal); remain awake.
5. Say `Thanks Jarvis, that's all`; sleep silently.
6. After wake, say `Thanks, Jarvis, one more question: what's seventeen times six?`; answer 102, remain awake.

No real Luna/action tool executes in overlap mode. Live model classification remains unproven until the Windows tests pass.
