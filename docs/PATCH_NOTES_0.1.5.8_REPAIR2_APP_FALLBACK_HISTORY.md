# 0.1.5.8 Repair 2 — Same-app launch fallback + local route history

### Motivation

User's live test: `Jarvis, open Discord` returned `unverified_user_intent` (not a `launch_windows_installed_app` failure); Spotify and File Explorer had separate results. Core previously only tried its first resolved OS registration. We must not confuse authorization denial with an executable/shortcut failure, or promise that a handoff proves a visible window.

### Changes

- Keep all same-turn Core authorization checks before any route selection or cached preference. Authorization-denied turns never retry or persist.
- When the first OS-discovered registered route refuses the handoff, try at most **two** other OS-discovered launch registrations with **exactly the same normalized app display identity**, subject to a best-effort 8-second total budget (does not interrupt a synchronous Windows API call).
- Stop on the first **Windows-accepted handoff**; never retry after acceptance (prevents duplicate launches). Acceptance does **not** mean Jarvis observed a window.
- Persist only the last Windows-accepted route per app plus the last 120 attempted handoffs to `%LOCALAPPDATA%\ORVEX\Jarvis\app_launch_history.json` (128-app maximum). It is local, not Git-tracked. No speech transcripts, browser URLs, or arbitrary commands are written.
- On subsequent uses, the previously accepted route gets preference **only if that exact route is present in the currently OS-discovered inventory**. The JSON file cannot inject a new executable path, and a failed cached route is evicted.
- Read-only `scripts/app_launch_history_probe.py` displays the launch summary; optional `--paths` reveals app installation paths only upon explicit command. Deleting the JSON resets cached preferences.
- Normal voice/conversation routing, browser policy, and UI remain untouched.

### Known limitations

- This candidate does not repair `unverified_user_intent` rejections automatically, because they occur **before** route launch attempts. If Discord still returns that code, capture the model-selected app name and the separately confirmed user transcript for the same turn. Do not bypass Core authorization.
- No arbitrary drive scans, shell/PATH launch, executable guessing, remote browser history, app closing, or verified window observation. Future versions can extend logs to file/browser actions via their own permission-aware integrations.
- Windows-specific OS route execution requires user live testing; automated tests are inert Linux-compatible mocks.

### Rollback

Uncommitted patch uses `.patch_backups/0.1.5.8_repair2_app_fallback_history` for the replaced module. New files are in the patch manifest. Leave backups until user acceptance; use a prior Git checkpoint to roll back if needed. Runtime launch-history file lives outside the repository; clearing it is optional.
