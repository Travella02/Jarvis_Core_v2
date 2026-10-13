# Repair16 Diagnostic1 — Windows live test

1. Install the diagnostic patch on top of **Repair16**. Do not roll back Repair16 first.
2. Verify tests: `python -m unittest tests.unit.test_0_1_3_repair16_diagnostic1 -v`, then `python -m unittest discover -s tests -v`, then `python -m core.diagnostics`.
3. Launch: `python .\scripts\realtime_ab.py mini-overlap-luna-trim`.
4. Wake with `Hey Jarvis`, then ask naturally: `Compare three production architectures for a multi-tenant AI assistant. Cover tenant isolation, authorization boundaries, retries, audit logging and trade-offs, and recommend one.`
5. If Core fails, locate `[Jarvis Luna Diagnostic] phase=core_failed` with `http_status`, `error_type`, `error_code`, `error_param`, `detail_class`, and `response_id_present`. Send screenshots of those lines along with nearby `[Jarvis Luna] phase=result`. **Never send your .env, API key, raw API response, request body, or an unredacted trace that may contain secrets.**
6. Ask one easy question after any failure to verify normal Mini playback still works, e.g. `What's nine times eight?`. Then `That's all, Jarvis.`
7. If delegation works, describe whether Jarvis actually speaks the *Core answer*, not just instructions to Luna. Track `phase=synthesis_completed` (voice generation) separately from real audible delivery.

Interpretation: HTTP 400 + `error_param` means inspect request shape for that parameter; 401/403 indicates auth/permission; 429 rate limiting; 5xx provider error. `detail_class=unclassified` means we still lack a safe structured cause. No automatic retries or speculative fallback were added.
