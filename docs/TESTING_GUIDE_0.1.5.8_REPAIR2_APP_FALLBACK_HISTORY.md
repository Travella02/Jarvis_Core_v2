# Windows acceptance — 0.1.5.8 Repair 2

1. From Jarvis project root, with Repair 1 already present, extract Repair 2 ZIP over root and run `python .\apply_0_1_5_8_repair2_app_fallback_history.py`. **STOP** if hashes don't match, and send current project ZIP. Do not force overwrite.
2. Test: `python -m unittest tests.unit.test_0_1_5_7_unified_desktop tests.unit.test_0_1_5_8_installed_app_discovery tests.unit.test_0_1_5_8_repair2_app_fallback -v`
3. Full tests: `python -m unittest discover -s tests -q` (no beeping from this candidate)
4. UI: `npm run desktop:build`
5. Optional inventory diagnostic: `python .\scripts\app_inventory_probe.py Discord Spotify`
6. Live: `python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-universal-apps`

## Standard five, in order

- `Hey Jarvis, what is seventeen times twenty-three?`
- `What planet is called the Red Planet?`
- `What is the capital of France?`
- `How are you doing today?`
- `Thanks Jarvis, that's all.`

## App checks

- `Hey Jarvis, open Discord.` — check for visible Discord app, not just a success log.
- `Close Discord manually, then open Discord again.` — should prefer cached accepted route if OS inventory contains it.
- `Jarvis, launch Spotify.` — check whether desktop app opens; do not infer from success message alone.
- `Jarvis, open File Explorer.` — verify a window.
- `Open YouTube.` then `Search YouTube for Sidemen.` — browser regression.
- `Don't open Discord.` — MUST NOT act.
- `Open Discord and Spotify.` — MUST NOT partially act.
- `Thanks Jarvis, that's all.` — sleep.

Examine history with `python .\scripts\app_launch_history_probe.py`; logs must show only attempted app handoffs, not denied utterances. If Discord still logs `unverified_user_intent`, fallback was intentionally not entered; collect the transcript, selected app, and ToolResult for that turn to diagnose authorization separately. Do not clean or commit before actual Windows acceptance.
