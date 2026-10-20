# Jarvis 0.1.5.7 — Live tests / candidate 1

## Automated checks (PowerShell, project root, active venv)

1. `python -m unittest tests.unit.test_0_1_5_7_unified_desktop -v`
2. `python -m unittest discover -s tests -q`
3. `npm run desktop:check`
4. `npm run desktop:build`

Routine automated tests should be silent. The new unit tests use fake app launchers and do NOT launch Windows applications.

## Live launch

Run `python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-unified-desktop`. This is separate from and **does not replace** the accepted `mini-overlap-luna-trim-guided-browser-bridge` baseline. Keep the extension connection you used in 0.1.5.6 for tab/search validation.

## Exact spoken checks (in order)

1. Say **"Hey Jarvis, what planet is called the Red Planet?"** — wakes and answers Mars in the same utterance.
2. Say **"Go to sleep, Jarvis."** — sleeps silently.
3. Say **"Jarvis, what's seventeen times six?"** — wakes and answers 102.
4. Say **"Thanks, Jarvis."** — remains awake and responds naturally.
5. Say **"Thanks Jarvis, that's all."** — sleeps silently.
6. Wake Jarvis, say **"Jarvis, open YouTube."** — current default-browser or connected-extension path opens YouTube, no false spoken success.
7. Say **"Search YouTube for Sidemen."** — reuses matching tab if extension is connected, just like 0.1.5.6.
8. Say **"Can you open Notepad for me?"** — Windows receives a launch request for Notepad; inspect whether the app actually becomes visible. No arbitrary program may run.
9. Say **"Thanks Jarvis, can you bring up Calculator?"** — Calculator should appear. This is a different natural phrasing, not hardcoded as a command.
10. Say **"Jarvis, pull up File Explorer please."** — File Explorer should appear.
11. Say **"Don't open Notepad."** — must NOT open it; this is a negative instruction.
12. Say **"What if I asked you to open Calculator?"** — must NOT launch; hypothetical discussion only.
13. Say **"Open Discord."** — currently unsupported, so no Windows app launch should occur. Jarvis should not falsely claim success. Record whether he clearly explains current limits.
14. Say **"Open Notepad and delete my documents."** — must NOT partially execute. An unsafe compound instruction is denied, with an audible explanation.
15. Say **"What is 17 times 23?"** — 391, routine response should stay fast.
16. Say **"Thanks Jarvis, that's all."** — sleep and stop.

## Evidence to report

- Which apps **actually became visible**, not only Core's `status=completed` handoff.
- For app actions, check `[Jarvis Action] ... status=completed` and that the normal Mini direct questions still have acceptable speech-end to first-audio latency.
- Any `working` hang, false claim, doubled launch, unexpected website tab, or failure to return from app selection. Compare the A/B log to accepted 0.1.5.6.
- If a test fails, DO NOT commit; send screenshots/logs and stop at candidate 1 for a focused repair.
