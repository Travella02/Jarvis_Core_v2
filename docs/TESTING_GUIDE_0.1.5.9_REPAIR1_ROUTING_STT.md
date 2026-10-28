# 0.1.5.9 Repair1 — Windows Install, Test & Cleanup

Jarvis must be CLOSED. Extract the patch archive into the existing project root; do not create a nested folder. Use the original existing Git repo and keep user data and settings intact. The guarded installer preflights all baseline and payload SHA-256 hashes before touching files, backs up replacements and aborts without modifying files on a mismatch. Never force it.

```powershell
python .\apply_0_1_5_9_repair1_routing_stt.py
```

```powershell
python -m unittest tests.unit.test_0_1_5_9_repair1_routing tests.unit.test_0_1_5_9_browser_result_selection tests.unit.test_0_1_5_8_repair4_return_search -v
```

```powershell
python -m unittest discover -s tests\unit -p "test_*.py" -q
```

```powershell
npm run desktop:build
```

```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-universal-apps
```

## Live acceptance
1. Five standard phrases: “Hey Jarvis”; “What is seventeen times twenty-three?” (391); “What planet is known as the Red Planet?” (Mars); “What is the capital of France?” (Paris); “Thanks Jarvis, that's all” (sleep). Check latency and continuity.
2. Wake again. “Jarvis, open YouTube.” Reuse the default browser. Try `Jervis OpenYouTube` if the natural STT produces joined words; no need to force a transcription artificially.
3. “Search YouTube for Sidemen.” Verify current YouTube search page, no duplicate tab.
4. “Play the first video.” Require `tool=browser_action`, `intent=select_result`, matching ordinal, verified navigation to first distinct YouTube watch result in the SAME tab. Don't require autoplay if browser policy blocks it.
5. Back to search results; “Open the second result.” Verify second distinct watch page.
6. “Pause the video.” “Resume the video.” “Make it fullscreen.” “Exit fullscreen.” Check effect or truthful failure, not a made-up claim.
7. “Don't play the third video” and “What if you played the first video?” MUST NOT cause navigation.
8. Disconnect browser extension and retry a numbered-result request: truthful audible failure, no unrelated tab launch.
9. Switch to Wikipedia and return to YouTube search to regression-test reuse, with no premature tool selection or speech leaking.

Capture routing, selected tool, accepted Core action, browser bridge operation, timings and any visible UI feedback. A single regression means retain the patch and backups, diagnose, and increment repair number rather than commit.

## ONLY AFTER live acceptance
Close Jarvis. Delete `apply_0_1_5_9_repair1_routing_stt.py`, `patch_files` (this repair's extracted payload), this in-repo repair ZIP if present, and `.patch_backups` (only temporary patch-generated backups, never unrelated data). Then run final tests and inspect `git status --short --untracked-files=all` and `git diff --check` before staging ONLY intended source/tests/docs. Commit once after clean checks. Keep the user-owned v1 reference unchanged.

Suggested commit: `fix(jarvis): repair 0.1.5.9 YouTube selection routing and STT boundaries`
