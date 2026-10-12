# Jarvis Core v2 0.1.3 Candidate Handoff

- Based on accepted 0.1.2 repair6-repair15 complete checkpoint, including V1 0.3.6 reference.
- New `mini-overlap-decisions-shadow` script runs accepted PCM and Realtime Mini *unchanged* while a backend-owned async Decisions classification observes only a user transcript.
- API key remains server-only; no request state stored and no user memory/actions/permissions/response routing touched.
- Read-only extra request to OpenAI costs money and can take longer than pure API call median due to transcript availability.
- `mini-overlap` keeps no shadow and should remain the golden live baseline.
- Actual action and Luna tool execution is not yet implemented; any selected probes remain dry run.
- Audio, UI, and wake/sleep are untouched; verify against accepted 0.1.2 five-phrase tests.
- Required workflow: apply ZIP -> unittest -> diagnostics -> desktop check -> live compare -> user accept -> clean temporary files -> commit.
- Do not claim 0.1.3 complete from automated tests alone.
