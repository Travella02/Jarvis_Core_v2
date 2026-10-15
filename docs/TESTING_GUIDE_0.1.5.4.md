# 0.1.5.4 — Managed Browser Foundation Live Test (Windows)

**Keep the last accepted 0.1.5.3 Repair1 Git checkpoint and patch ZIP until all live tests pass.** Close Jarvis before install and between A/B launches. Extract patch ZIP to the project root, not a nested folder.

## 1. Apply the guarded patch
```powershell
python .\apply_0_1_5_4_managed_browser.py
```

## 2. Optional managed browser dependency (one-time)
```powershell
python -m pip install -r .\requirements-browser.txt
```
```powershell
python -m playwright install chromium
```
This installs the optional Playwright-controlled browser. On Windows the adapter first tries the installed Microsoft Edge using an isolated ORVEX profile; bundled Chromium is the fallback. Neither install command touches your existing Chrome/Edge browsing profile.

## 3. Tests (no intentionally audible beeps)
```powershell
python -m unittest tests.unit.test_0_1_5_4_managed_browser -v
```
```powershell
python -m unittest discover -s tests -q
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

## 4. Start separate comparison runs
Accepted 0.1.5.3 control mode:
```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-semantic
```
Experimental browser foundation:
```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-managed-browser
```

## 5. Five canonical regression phrases (speak naturally)
1. “Hey Jarvis, what planet is called the Red Planet?” → wakes and answers Mars.
2. “Go to sleep, Jarvis.” → sleeps without unnecessary response.
3. “Jarvis, what's seventeen times six?” → wakes and answers 102.
4. “Thanks, Jarvis.” → stays awake and acknowledges normally.
5. “Thanks Jarvis, that's all.” → sleeps silently.

## 6. Browser live acceptance in the new mode
1. Wake again and say “Jarvis, could you open Google for me?” → opens a separate Jarvis-managed Edge/Chromium browser at Google; no spoken confirmation; Working returns to Ready.
2. “Thank you! Now open Wikipedia please.” → new tab in the managed browser; no ordinary direct-question delay.
3. “Go back to the previous page.” → **only** if current tab has prior navigation history, otherwise a short truthful audible failure; no unintended new tab.
4. “Switch to the next tab.” → focuses the other Jarvis-managed tab.
5. “Close the current tab.” → closes only that managed tab; not the Jarvis app.
6. “Can you search YouTube for how black holes form?” → YouTube results page; search terms encoded; no random other website.
7. “Can you search the web for the James Webb telescope?” → Google search results.
8. “Don't open YouTube.” → **must not** open anything.
9. “If you get a chance, open GitHub.” → **must not** open anything until a clear immediate instruction; may simply respond conversationally.
10. “Open YouTube and send an email.” → **must not** execute any part of this unsupported combined action.
11. Ask “What is seventeen times twenty-three?”, “What planet is called the Red Planet?”, “What is the capital of France?” between browser actions. Compare response-to-first-audio with the control arm over repeated runs (p50/p95 if possible). Ordinary conversational speed must remain comparable.
12. Put Jarvis to sleep while the managed browser is open; tabs should remain available while Jarvis sleeps and after wake. Closing the **desktop app** should shut down the managed browser.
13. Interrupt or change your request during a slow browser navigation. No *stale verbal claim* may arrive after the next turn. An already-started site navigation may complete; never interpret cancellation as guaranteed undo.
14. Ask for browser playback/click/form automation not yet implemented. Jarvis should explain the limitation rather than pretend it acted.

## 7. Failure cues
- `browser_dependency_missing`: install Playwright dependency in active venv.
- `browser_start_failed`: managed Edge/Chromium could not launch, check profile lock and Playwright Chromium install.
- `unverified_user_intent`: Core could not bind the proposed site/action to exact current user words.
- `not_available`: no existing page/tab/history for the requested operation.
- `unverified_timeout`: browser status unknown; verify browser visually before retrying.
- `desktop_action_feedback reason=result_timeout`: Core status did not reach UI; report screenshot/log, do not assume success/failure.

Do not commit or remove patch/backups until Windows live acceptance. After approval, inspect `git status --short`, remove patch ZIP, apply script, extracted patch payload and backup folder, re-run relevant checks and commit with a checkpoint message.
