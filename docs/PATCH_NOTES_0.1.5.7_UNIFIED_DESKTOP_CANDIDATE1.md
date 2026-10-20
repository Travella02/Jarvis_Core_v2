# Jarvis Core v2 0.1.5.7 — Unified Desktop Actions, Candidate 1

**Candidate only. DO NOT COMMIT before live acceptance.**

## Scope

- Retain the accepted `mini-overlap-luna-trim-guided-browser-bridge` A/B setup byte-for-byte in its functionality. Add a **separate opt-in** `mini-overlap-luna-trim-guided-unified-desktop` mode.
- Mini can propose `browser_action` (existing) or `launch_app` (new). Both share the same existing first Mini tool-selection pass, transcript-binding gate and Core action result handling. No additional model API request is added to normal conversations.
- In this first implementation only **Notepad, Calculator, and File Explorer** are executable app targets. Each is mapped by Core to a fixed Windows system application. The model cannot submit executable paths, arguments, PowerShell commands, or shell strings.
- Core independently verifies the same authenticated local desktop turn, committed user transcript, immediate app-launch language, app identity, exclusion of negation/hypothetical/compound/mismatched requests, and per-turn idempotency.
- Desktop uses Windows' system directory instead of searching PATH or launching model-provided paths. A successful Windows OS handoff is logged as **handoff accepted**, not as a verified visible window. A failed launch produces an audible failure message.
- Existing browser bridge/extension, phonetic wake/sleep and fast conversational route are unchanged. The new capability can operate without an active browser extension connection, but browser tab control still requires a compatible extension.

## Explicit limitations

1. **Not yet general application discovery.** Discord, Spotify, games and arbitrary Windows apps are NOT launchable through the new tool in this candidate; other action types remain unchanged.
2. Windows may accept an app-launch request without displaying a window. As V1 ISSUE-258 documents, **OS handoff is not window verification**. Never interpret `window_visible_verified=False` as an observed opened app. Visible app verification, process identity, and learned installed-app catalog are future milestones.
3. Not a general window-management, file-access, email, command-execution or multi-action automation capability. No credentials, elevated actions, or hidden launches.
4. The chosen browser for websites remains the OS default. Named browser launches and first-class site-vs-installed-app preferences require explicit later user controls.
5. Model classification of ambiguous names still requires live testing; Core must reject requests that lack independent user evidence. Users need not say exact scripted wording, but an ambiguous/unsafe turn is denied rather than guessed.

## V1 comparison (read only)

Reviewed V1 `jarvis/computer/apps.py` and issues 256, 258, 260. V1's asynchronous app discovery could slow launch by ~20 seconds, and shell acceptance could be mistaken for visible success. This slice deliberately avoids synchronous inventory scans and does not copy the full V1 service into V2; the reusable findings are independent authority, exact names/identity before fuzzy matches, an eventual prewarmed catalog, and launch verification.

## Installation

Extract the ZIP at the **Jarvis_Core_v2 root**, then run the root `apply_0_1_5_7_unified_desktop.py`. Preflight validates the exact 0.1.5.6 Search Repair 2 file contents using normalized SHA256 and refuses a drifted checkout (including if a previous patch is partially applied). Backups are stored under `.patch_backups`. Never force this installer past a STOP message. If drifted, upload the updated clean ZIP for rebuilding.

## Acceptance

Follow `docs/TESTING_GUIDE_0.1.5.7_UNIFIED_DESKTOP_CANDIDATE1.md` and check repeated browser search, two named built-in apps, natural wording, denial/failed action speech, and five standard wake/sleep regressions. Compare Mini direct response speed and quality with the accepted 0.1.5.6 Browser Bridge baseline. Run full suite and the Windows desktop build before live tests.

After **all** checks pass and user live-accepts: delete the patch ZIP, apply script, payload folder and `.patch_backups` created by this update; verify Git status; commit one checkpoint. Do not advance to 0.1.5.8 before acceptance.
