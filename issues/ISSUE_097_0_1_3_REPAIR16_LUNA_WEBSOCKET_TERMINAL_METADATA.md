# Issue 097 — Luna WebSocket terminal metadata omitted

**Observed:** Repair16 Diagnostic2 Windows run attached correct provider response ID but printed `model=n/a`, `output_limit=n/a`, `incomplete_reason=unknown`, `output_tokens=n/a`. An incomplete provider response with partial output had been confirmed.

**Cause in code:** `OpenAIProvider._stream_response_websocket` omitted `requested_model`, `requested_output_limit` (present in HTTP path), and called `_set_request_diagnostics` on terminal events without `_safe_response_telemetry(response)`. The response ID was captured from the created event, so the desktop log matched a diagnostic record missing terminal scalars.

**Fix scope:** Capture requested model/cap and a privacy-whitelisted terminal response status, incomplete reason, and token usage inside WebSocket provider *before Core sees the terminal event*. No change to responses, speech, cancellation, Core authority or model budgets.

**Acceptance:** Focused WebSocket simulations pass for incomplete, completed, unknown reason, response-ID correlation, privacy. Windows live evidence shows model/limit/status and provider-provided reason/usage if supplied. Actual Luna answer still needs separate validation.
