# Jarvis Core v2 0.1.3 Repair16 Diagnostic3 — WebSocket terminal metadata

## Confirmed cause of missing diagnostics
On Windows, Diagnostic2 showed `diagnostic_match=true`, `model=n/a`, `output_limit=n/a`, `incomplete_reason=unknown`, despite an incomplete provider response. The HTTP Responses stream records requested model/output limit and safe terminal response metadata; the WebSocket Responses stream previously did not record those same fields. The request uses WebSocket for Luna when enabled. This is a confirmed **diagnostic instrumentation gap**, not proof of the provider's underlying reason for incompletion.

## Scope
- `providers/intelligence/openai/provider.py` WebSocket path now retains the actual submitted model and `max_output_tokens` and whitelisted metadata from the terminal Responses event **before** passing completion/failure to Core.
- Reuses existing `response_diagnostics` by exact provider response ID and existing `Jarvis Luna Budget` safe-format logger from Diagnostic2. No raw body, tokens-as-text, user prompt, credentials, arbitrary provider error, or response IDs are printed.
- New isolated WebSocket tests for incomplete and completed terminal events, exact request budget, privacy, mismatched response IDs and preservation of unchanged failure voice.

No model, routing, startup, trim, sleep, action authorization, TTS, token limit, retry, Core execution, or voice-response behavior change. This applies on top of installed Repair16 Diagnostic2 (and Diagnostic1/Repair16) following committed Repair15.

## Acceptance
Live `[Jarvis Luna Budget]` should now contain `model=gpt-...`, `output_limit=256` unless locally overridden, and `response_status=incomplete` if the provider returned incomplete. It should show `incomplete_reason=max_output_tokens` or `content_filter` only if supplied. Missing metadata remains `n/a` or `unknown` rather than fabricated. The underlying Core failure is *not fixed by this patch*. Do not commit or cleanup until actual Luna answer delivery and cancellation work.
