# 0.1.5.8 Repair 4 — testing guide

1. Start from your committed, working **Repair 3** checkout. Stop Jarvis; do not apply on a dirty or different baseline.
2. Extract the entire ZIP in the repository root, preserving the `patch_payload_*` folder. Run `python .\apply_0_1_5_8_repair4_return_search.py`. If `STOP` appears, do not force the patch.
3. Run targeted tests:
   `python -m unittest tests.unit.test_0_1_5_6_browser_bridge tests.unit.test_0_1_5_6_browser_bridge_search_repair2 tests.unit.test_0_1_5_8_repair3_tab_reuse tests.unit.test_0_1_5_8_repair4_return_search -q`
4. Run full unit tests: `python -m unittest discover -s tests -q` and UI build: `npm run desktop:build`.
5. Start: `python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-universal-apps`.

## Standard five live voice tests (first)
1. `Hey Jarvis, what is seventeen times twenty-three?`
2. `What planet is called the Red Planet?`
3. `What is the capital of France?`
4. `How are you doing today?`
5. `Thanks Jarvis, that's all.`

## Browser acceptance (same extension and env configuration; no extension changes in Repair 4)
1. `Hey Jarvis, search YouTube for Sidemen.` Verify results.
2. `Open Wikipedia.` Verify a separate tab.
3. `Hey Jarvis, can we go back to YouTube and search for soccer videos?` Verify ORIGINAL YouTube tab is reused and Wikipedia remains intact. Watch for `[Jarvis Browser Route] operation=search | route=reused_connected_tab | accepted=True`.
4. `Switch back to the YouTube tab and search for Rocket League.` Same expectation.
5. `Don't search YouTube for anything.` No action.
6. `Open Discord`, `Open Spotify`, and `Open File Explorer` for regression checks. Do not change app handling in this repair.

If Jarvis routes a composite command to `select_tab` without a search query, Core intentionally rejects it rather than guessing. Record the selected `browser_action` arguments and failure code for diagnosis; do not weaken authorization.

**Cleanup after live acceptance:** remove only this repair ZIP, `apply_0_1_5_8_repair4_return_search.py`, its extracted `patch_payload_*` directory, and its `.patch_backups/0_1_5_8_repair4_return_search` folder; verify `git status --short` before committing. Keep the changed source/tests/docs/issues.
