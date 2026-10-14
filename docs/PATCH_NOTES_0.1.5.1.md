# Jarvis Core v2 — 0.1.5.1 (Tool Gateway Foundation)

Candidate milestone based **only** on user-accepted 0.1.4 (`f6f8a5a` reported in Git logs). No 0.1.4.2 experimental mic, VAD, or response-completion code has been imported.

## New
- `CoreToolGateway`: Core-owned, non-model executor for one registered capability (`desktop_browser/open_approved_site`).
- Independent `ConfirmedUserAction` authorization, scoped to the exact turn and local trusted desktop. ToolRequest alone never grants authority.
- Extremely conservative explicit-utterance gate and exact site allowlist (YouTube only). **No arbitrary URLs, subprocesses, shell, account actions, or filesystem mutations.**
- In-memory duplicate side-effect prevention, including concurrent requests and failed launches. Precise distinction between browser launch accepted and verified page load.
- A manual `--open-youtube` demonstration that invokes the true OS default browser; default mode is simulated.
- Focused offline tests with fake browser launchers. These make no paid API requests, network connections, browser launches, or beeps.

## Intentionally not yet wired
- **Voice and typed Jarvis do NOT open websites in this patch.** Model-side `test_action` remains DRY RUN; do not claim otherwise. The next 0.1.5 slice will connect verified voice/typed requests through the existing WebRTC/desktop Core bridge after foundation acceptance.
- Permissions here are a restrictive single-user local foundation; persistent identity, approval prompts, auditable actions, retry policy, and OS-level completion verification remain future work.
- Replay cache lives per gateway instance; persists neither sessions nor process restarts. Reuse requires future durable idempotency support.
- The existing baseline's outdated top-level version fields are not rewritten by this focused patch. `docs/RELEASE_MANIFEST_0.1.5.1_CANDIDATE.json` tracks this candidate. Version metadata reconciliation remains scheduled.

## No changes
- Existing Realtime Mini provider, Luna delegation, wake/sleep, PCM onset, audio, barge-in, and all UI files.
- Old legacy provider tool-selection probes remain dry runs. No new automatic cost or API request.

No commit until tests and manual acceptance. Preserve backups and patch until accepted.
