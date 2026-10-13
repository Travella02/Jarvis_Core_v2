# Jarvis 0.1.3 Repair16 Diagnostic2 — incomplete Luna responses

## Confirmed from Windows live test
Mini selected `ask_luna`, Core executed the primary route, provider returned a response identifier and partial text, but Core returned `detail_class=incomplete_response` with no HTTP error. The Core voice request uses `JARVIS_OPENAI_VOICE_MAX_OUTPUT_TOKENS`, default **256** tokens. An output-token budget limit is plausible, not yet proven.

## Change (diagnostic only)
- `providers/intelligence/openai/provider.py`: stores bounded, structured telemetry from Responses API terminal events: `incomplete_details.reason`, actual response status, output/input token counts, reasoning token count (when supplied), selected request model and request output-token budget. Links telemetry using **exact provider response ID**; never grabs an unrelated latest request.
- `apps/desktop_luna.py`: prints a separate `[Jarvis Luna Budget]` line for current Core result. Only safe numeric tokens, known incomplete reasons, a model matching restricted `gpt-*` form, and diagnostic-match boolean. No raw completion, request, response ID, exception message, trace, API key, or HTTP body is printed.
- Adds focused simulation tests for incomplete response, privacy, route/ID matching and unchanged failure voice.

**No automatic model swap, retries, output budget increase, voice/routing change, action permission change, or incomplete-result playback.** This patch is an add-on to **Repair16 Diagnostic1**, which itself follows Repair16, on top of committed Repair15. Do not restore earlier patch versions.

## Determining the cause
If the live line shows `incomplete_reason=max_output_tokens` and `output_tokens` at the cap, run the same question in a *separate process* with temporary PowerShell override `$env:JARVIS_OPENAI_VOICE_MAX_OUTPUT_TOKENS = '1024'` (see guide). The existing default budget is unchanged by the patch. If the reason is not `max_output_tokens`, **do not raise the cap as a purported fix**; investigate the reported reason instead.

Do not commit or delete patches/backups until delegated Luna answers have succeeded, were actually spoken, and interruption/cancellation tests have passed.
