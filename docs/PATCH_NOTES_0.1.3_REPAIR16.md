# 0.1.3 Repair16 — Verified Core/Luna delegation and stale-result test mode

**Based on accepted, committed Repair15** (post-Repair14 rollback). No live acceptance claimed.

- Adds `mini-overlap-luna-trim-cancel-test` launcher; otherwise identical to accepted `mini-overlap-luna-trim` except `JARVIS_LUNA_RESULT_HOLD_SECONDS=8` (only when explicitly launched).
- Keeps real Core/Luna reasoning, Core authority, private PCM gate, no action execution, no Decisions shadow, no compact routing.
- Adds deterministic tests for launcher isolation and backend stale-result quarantine; read-only, transcript-free summary report.
- No core, renderer, STT/TTS, voice policy or routing algorithm changes. Existing tests for Core delegation and cancellation remain authoritative.
- Objective: verify live end-to-end Core execution, spoken result, no unauthorized action or stale speech; reject the milestone if those cannot be observed.
- Python suite and diagnostics: locally passed. Desktop Electron check: passed. Full Vite build: **not available in this environment**, must be performed on Windows.

See `docs/TESTING_GUIDE_0.1.3_REPAIR16.md` for procedures and mandatory five standard phrases.
