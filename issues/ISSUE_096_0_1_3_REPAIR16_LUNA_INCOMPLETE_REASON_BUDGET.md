# Issue 096 — Incomplete Luna response lacks reason/usage diagnostics

**Evidence:** Repair16 Diagnostic1 Windows run, `route=primary`, `phase=core_failed`, `detail_class=incomplete_response`, `response_id_present=True`, `partial_text_present=True`, no HTTP status, about 5.1 seconds elapsed. Default OpenAI voice request budget is 256 output tokens, but no provider incomplete reason/usage available in terminal.

**Risk:** Prematurely raising token budgets increases costs and may not solve errors unrelated to output limits. Logging raw provider content risks secrets/user text exposure. Mixing concurrent provider turns risks attaching the wrong diagnostics.

**Diagnostic2:** Capture bounded integer usage + reason from response terminal event under exact provider response ID, surface sanitized fields only at Core result, keep failure playback and routing untouched. Add simulation tests. No claim of a fix until live run proves cause; then controlled 256 vs 1024 output-budget experiment if provider says `max_output_tokens`.

**Acceptance:** Underlying reason is visible without raw payload, Mini pipeline remains intact, then actual delegated result and cancellation paths are separately verified.
