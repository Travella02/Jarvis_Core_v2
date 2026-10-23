# Jarvis 0.1.5.9 Candidate 1 — Windows Live Testing

## Install (repo root, while Jarvis is CLOSED)
1. Make sure the prior 0.1.5.8 Repair4 checkpoint is committed and the working tree is clean. Extract the entire ZIP into `Jarvis_Core_v2` (not into a nested folder).
2. Run the installer and wait for `APPLIED`. The installer refuses any baseline hash mismatch and backs up modified files; do not use force overwrites.
3. Run the focused unit tests (silent) and the desktop build.
4. Start the exact existing Jarvis A/B launcher mode `mini-overlap-luna-trim-guided-universal-apps`. Keep the authorized Jarvis browser extension connected; no browser-extension reload is needed for this candidate.

```
python .\apply_0_1_5_9_candidate1_browser_result_selection.py
```

```
python -m unittest tests.unit.test_0_1_5_9_browser_result_selection tests.unit.test_0_1_5_8_repair4_return_search tests.unit.test_0_1_5_6_browser_bridge -v
```

```
python -m unittest discover -s tests\unit -p "test_*.py" -q
```

```
npm run desktop:build
```

```
python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-universal-apps
```

## Five standard voice tests (check latency too)
1. “Hey Jarvis.”
2. “What is seventeen times twenty-three?” Expected: 391.
3. “What planet is known as the Red Planet?” Expected: Mars.
4. “What is the capital of France?” Expected: Paris.
5. “Thanks Jarvis, that's all.” Expected: sleep.
Wake Jarvis again before browser actions.

## Browser tests
1. “Jarvis, open YouTube.” Check that it opens in OS default browser as usual.
2. “Search YouTube for Sidemen.” Check reuse of YouTube tab (no extra tab).
3. While YouTube search results are active, say “Play the first video.” Expected: the verified FIRST distinct watch result opens in the SAME YouTube tab. Autoplay itself may be blocked by the browser, so visually check the watch page; do not infer playback success from the navigation status.
4. “Pause the video.” “Resume the video.” “Set video volume to forty percent.” “Make it fullscreen.” “Exit fullscreen.” Each must have a visible effect or an audible failure.
5. Go back to search results and say “Open the second result.” Confirm the SECOND distinct watch result opens in the SAME tab.
6. Negative and hypothetical safety: “Don't play the third video” and “What if you played the first video?” Must NOT navigate.
7. Switch to Wikipedia and repeat YouTube return/search from previous Repair4; tab reuse must still pass.
8. Disconnect the extension and repeat “Play the first video.” It must fail audibly and NOT open an unrelated or new tab.

## Logs to capture
`[Jarvis Browser Route] operation=select_result | route=selected_video_same_tab | accepted=True` for a successful selection. For mismatch/unavailable cases, expect `accepted=False` with a safe reason. For screenshot reviews, include tool, action, and latency lines.

## Cleanup before committing
After tests pass, close Jarvis, delete `apply_0_1_5_9_candidate1_browser_result_selection.py`, `patch_payload_0_1_5_9_candidate1_browser_result_selection`, and `.patch_backups` from your repo root. Confirm `git status` contains only the intended project files. Suggested commit: `feat(jarvis): add verified YouTube result selection and fullscreen controls`.
