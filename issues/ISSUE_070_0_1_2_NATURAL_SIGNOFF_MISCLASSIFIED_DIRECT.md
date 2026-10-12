# ISSUE 070 — Polite closure routed as direct instead of sleep

**Status:** Model instruction correction validated in unit/integration tests; live validation pending.

Observed: `USER SPEECH="Thanks Jarvis, that's all."` -> `route=direct | owner=realtime` -> audible "Anytime, happy to help...". The transcript was accurate and bridge never saw `route=sleep`, so the failure was the model's route selection. Existing lifecycle implementation already handles `route=sleep` silently.

Correction: Teach the internal router that polite gratitude plus clear end-of-session language (in natural order variations) is a `sleep` intent, while standalone gratitude or continued requests are not. No hard-coded lexical fast path; no permission/action changes; model can still misclassify and must be live tested.

Separate evidence: Repair6 shadow does run, but speculative Realtime first token (462 ms) followed routing (397 ms); Luna lacked a pre-route token and one transcript arrived after route. This does not yet justify speculative audio buffering. A/B measurement is required to isolate overhead.
