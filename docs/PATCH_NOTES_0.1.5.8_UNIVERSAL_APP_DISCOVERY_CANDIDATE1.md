# Jarvis 0.1.5.8 Candidate 1 — Discovered Windows Applications

## What changes
- New opt-in A/B mode `mini-overlap-luna-trim-guided-universal-apps`; **the existing `...unified-desktop` mode is unchanged by default**.
- Core quietly preindexes user/common Start Menu shortcuts (`.lnk`, `.appref-ms`) and registered Windows App Paths, with stable fallback system apps. No whole-disk scan, no need to program per-user applications into the LLM schema.
- Mini can propose any app **display name** through the `launch_app` tool, with no executable path or shell arguments. Core independently resolves a unique installed target and validates the confirmed same-turn spoken request. Misses and ambiguity fail closed.
- Reuses V1 lessons: prefer known OS app routes over deep scans, resolve exact display/brand aliases before approximate matches, and do not treat a Windows launch handoff as proof a window appeared.
- File Explorer uses the Windows directory rather than assuming explorer.exe lives in System32.
- Browser tools, permissions, speech/VAD/PCM, wake/sleep, and Core delegation are not changed in this update.

## Deliberate limitations
- Discovery is **not yet all apps**. UWP-only apps without Start Menu shortcuts, Steam-only games, portable programs without registered shortcuts, and files may require later adapters.
- Windows launch handoff may succeed without a visible window; `window_visible_verified` remains false until a separate verified-window-control patch. Do not claim visual verification.
- Close/minimize/focus, user-defined aliases, file search, installation and potentially destructive workflows are **not** in scope.
- This is experimental and should NOT replace the 0.1.5.7 baseline until Windows live acceptance.
- No arbitrary commands, URLs, model-selected executable paths, extra launch arguments or shell interpreter use.

## V1 reference compared
The reference archive `Reference_jarvis_corev1/Jarvis_0.3.6_clean_checkpoint.zip`, notably `jarvis/computer/apps.py` and Issues 258/260, informed the design. We did not port its broad scanning, script/command support or older authority model; Core remains sole executor.

## Candidate acceptance
Exact 0.1.5.7 Candidate 1 installed files must match the hashes in the patch manifest, otherwise **STOP** with no changes. Automated Windows tests plus live observation required before cleanup or commit.
