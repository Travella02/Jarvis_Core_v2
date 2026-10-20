# Jarvis 0.1.5.8 Candidate 1 — Windows acceptance

## Before application
- Make sure Jarvis/Electron is closed and `git status --short` contains only the currently accepted 0.1.5.7 working files (or is clean if you checkpointed).
- Extract the provided ZIP to the **project root**; do not move the `patch_payload_*` folder into apps/ or scripts/.
- Run `python .\apply_0_1_5_8_universal_apps.py`. If it prints STOP, do not force it; upload an updated clean ZIP and current `git status --short`.
- Do not clean or commit before live tests pass. After acceptance delete the patch apply script, patch payload, and patch-specific backup folder before committing.

## Automated tests (PowerShell; one step at a time; venv active)
`python -m unittest tests.unit.test_0_1_5_7_unified_desktop tests.unit.test_0_1_5_8_installed_app_discovery -v`

`python -m unittest discover -s tests -q`

`npm run desktop:check`

`npm run desktop:build`

## Live A/B
Stable control: `python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-unified-desktop`

New candidate: `python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-universal-apps`

Check the launch line reads `universal_apps=on` for candidate and `universal_apps=off` for control. Neither requires a second LLM routing call. The browser extension is relevant only to tab/media control, not app discovery.

## Five standard baseline voice phrases
1. "Hey Jarvis, what is seventeen times twenty-three?" — answer 391.
2. "What planet is called the Red Planet?" — answer Mars.
3. "What is the capital of France?" — answer Paris.
4. "How are you doing today?" — short, natural response.
5. "Thanks Jarvis, that's all." — sleep silently.

## Application/intent tests (wake again)
1. "Jarvis, open File Explorer." — confirm Explorer truly appears; no web tab.
2. "Could you open Notepad for me?" — Notepad appears.
3. "Thanks Jarvis, could you bring up Calculator?" — Calculator appears.
4. "Jarvis, open Discord." — *installed Discord* app should open, not discord.com in a browser. If Discord isn't installed, an honest spoken failure.
5. "Jarvis, launch Spotify." — installed app should open, without an app-name-specific patch.
6. "Jarvis, open Chrome." — launch installed browser app (if installed), not a Google search. Chrome could be branded as Google Chrome.
7. "Jarvis, open YouTube." — uses existing default-browser path.
8. "Search YouTube for Sidemen." — uses existing browser bridge tab where connected, unchanged.
9. "Do not open Discord." — must NOT launch.
10. "What if I asked you to open Discord?" — discussion only, must NOT launch.
11. "Open Discord and Spotify." — must NOT partially execute a compound request; no app launched.
12. "Please open an application that isn't installed." — must not invent success.
13. "Jarvis, that's all." — sleep.

## Report
- Give the exact spoken phrase and whether a real *window* appeared, not only the `status=completed` log.
- Note if the first launch after wake fails while a second works (app inventory warmup), any wrong route to browser, slow conversational turns, duplicate launches, or an unexplained audible confirmation on visible success.
- Do not run arbitrary unknown programs to test; choose ordinary apps you know are installed.
- **Windows user acceptance is required**. Linux unit tests cannot prove Windows installed-app behavior.
