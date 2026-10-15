# 0.1.5.6 Candidate1 — Apply and Live Acceptance

**DO NOT COMMIT** until the live test is accepted. Quit Jarvis before applying.

**Installer repair1:** exact ZIP baseline verified. Only LF versus CRLF line-ending differences are now accepted; actual source changes still stop installation with hashes and line-ending diagnostics. The patch payload is unchanged.

## Apply (PowerShell, separate commands)

```powershell
python .\apply_0_1_5_6_browser_bridge.py
```

```powershell
python -m unittest tests.unit.test_0_1_5_6_browser_bridge -v
```

```powershell
python -m unittest discover -s tests -q
```

```powershell
npm run desktop:build
```

## Pair with an existing default browser (Chrome or Edge alpha)

1. In Windows Settings → Apps → Default apps, verify your default browser.
2. In that browser, open `chrome://extensions` (Chrome) or `edge://extensions` (Edge), enable Developer mode, then **Load unpacked** and choose `<Jarvis_Core_v2>\extensions\jarvis_browser_bridge`.
3. On the browser's extensions page copy the 32-character **ID** for `Jarvis Browser Bridge`. It should contain lowercase letters a through p.
4. Back in the same PowerShell where you start Jarvis, assign the extension ID you just read (replace the sample). This env variable is kept outside Git; never hardcode or commit it.

```powershell
$env:JARVIS_BROWSER_BRIDGE_EXTENSION_ID = 'PASTE_THE_32_CHARACTER_EXTENSION_ID'
```

5. Start Jarvis **after** setting that environment variable:

```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-browser-bridge
```

6. If extension connected, reload the extension once after Jarvis starts (or wait approximately 30 seconds for its reconnect alarm). If Core is unavailable or not paired, `open/search` still use Windows default and tab/media actions report unavailable.

## Live tests — 5 standard voice checks, then browser

### Five recurring voice tests (exact)
1. “Hey Jarvis, what planet is called the Red Planet?” → Mars, in one utterance.
2. “Go to sleep, Jarvis.” → sleeps silently.
3. “Jarvis, what's seventeen times six?” → 102, in same wake utterance.
4. “Thanks, Jarvis.” → remains awake and acknowledges naturally.
5. “Thanks Jarvis, that's all.” → sleeps silently.

### Browser bridge tests

1. “Open YouTube.” → system default browser; no spoken success. Leave the YouTube tab open.
2. “Search YouTube for Sidemen.” → **reuse the existing YouTube tab** rather than opening another. Verify search results.
3. “Open Google.” → default browser, no new managed window.
4. “Switch to YouTube.” → activate existing YouTube tab. “Switch to Google.” → activate existing Google tab.
5. Manually play a YouTube video first. Then ask “Pause the video.”, “Resume the video.”, “Mute the video.”, “Unmute the video.”, and “Set volume to 40 percent.” → verify actual video/player state and truthful reporting.
6. “Close the YouTube tab.” → target only a unique matching tab. “Next tab.” should switch among remaining tabs. NEVER close the user's unrelated tabs.
7. With Jarvis asleep, say “Jervis, what's seventeen times six?” and “Dervis, what's seventeen times six?” → verify phonetic wake behavior from the prior update.
8. Negative cases: “Don't close the Google tab.”, “Tomorrow open YouTube.”, “Open Google and send an email.” → no browser action.
9. Test extension disconnected (disable extension): “Open Wikipedia.” still opens via default-browser fallback, whereas “Pause the video.” should produce a short audible inability report.
10. Check same fast latency as before: simple turns should not have an added routing/model call.

**Not expected to work yet:** “Play the first Sidemen video”, arbitrary page clicking, cross-browser tab control without an extension, and video fullscreen. Record these as unsupported; do not score as an unexpected regression.

## Accept/reject, cleanup, commit

Report screenshots/logs plus whether the webpage actually changed. If anything fails, keep patch and backups; do not commit. If all acceptance cases pass, remove the installer ZIP/payload and `.patch_backups/0_1_5_6_browser_bridge_candidate1` for this patch *after verifying backups are no longer needed*, check `git status --short`, then commit. Never remove your embedded `Reference_jarvis_corev1` folder.
