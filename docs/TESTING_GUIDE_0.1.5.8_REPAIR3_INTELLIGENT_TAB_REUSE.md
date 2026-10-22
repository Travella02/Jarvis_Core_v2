# Repair 3 — Windows acceptance checklist

## Install

1. Stop Jarvis. Confirm local branch is the committed **Repair 2** baseline and that no patch file or `.patch_backups` remains in the working root.
2. Extract the entire Repair 3 ZIP into the `Jarvis_Core_v2` root. It contains a hash-checked installer and payload folder; do not move payload files individually.
3. Run `python .\apply_0_1_5_8_repair3_intelligent_tab_reuse.py`. If it prints `STOP`, do not force or manually overwrite files; upload a fresh clean checkpoint to investigate.
4. Run `python -m unittest tests.unit.test_0_1_5_6_browser_bridge tests.unit.test_0_1_5_6_browser_bridge_search_repair2 tests.unit.test_0_1_5_8_repair3_tab_reuse -v`.
5. Run `python -m unittest discover -s tests -q` and `npm run desktop:build`. Unit tests are silent by design.

## Standard five live conversation tests

- `Hey Jarvis, what is seventeen times twenty-three?`
- `What planet is called the Red Planet?`
- `What is the capital of France?`
- `How are you doing today?`
- `Thanks Jarvis, that's all.`

## Browser reuse live test (requires connected Chrome/Edge browser extension)

1. The existing unpacked `extensions/jarvis_browser_bridge` extension must be installed in the actual **default browser** being tested, enabled, and **reloaded** after this patch. Use its existing authorized extension ID in `JARVIS_BROWSER_BRIDGE_EXTENSION_ID`; do not invent IDs. This is an alpha developer-only permission step; there is not yet automatic first-run onboarding.
2. Start `python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-universal-apps`.
3. `Hey Jarvis, open YouTube.` — verify visually in the default browser.
4. `Search YouTube for Sidemen.` — **same tab** should navigate if bridge is connected; log should show `[Jarvis Browser Route] operation=search | route=reused_connected_tab | accepted=True`.
5. `Open Wikipedia.` — different-site action should not replace the YouTube tab. Expect an OS-default browser handoff.
6. `Go back to YouTube.` — if supported by connected extension, check tab select (a separate user request).
7. `Don't search YouTube for anything.` — must not execute.
8. `Open YouTube and Discord.` — compound tool request should not silently perform one half.
9. After each action verify app launches from Repair 2: `Open Discord`, `Open Spotify`, and `Open File Explorer`. Re-run the app launch-history probe if needed.

## If the search opens a new tab

Look at the `route=` value, NOT merely the tool's `status=completed`:

- `default_bridge_disconnected`: extension isn't authorized/connected; default OS browser handoff was expected, and the new tab is NOT a reuse regression.
- `default_extension_outdated`: installed browser worker hasn't reloaded or lacks the required guarded navigation capability; reload the unpacked extension.
- `default_ambiguous_tabs`: multiple matching site tabs and no safe focus/history tie-breaker; do not choose one arbitrarily.
- `reused_connected_tab`: verify the actual tab ID and URL; if it still created a new tab, collect the matching `[Jarvis Browser Route]` and bridge connection status.
- `bridge_command_failed` / `navigation_not_verified`: not successful; Jarvis should not silently retry or claim tab reuse.

Do not delete patch/backups or commit before Windows live verification. After acceptance, delete patch ZIP, extracted installer, payload and `.patch_backups`, then check `git status --short` before creating a checkpoint commit.
