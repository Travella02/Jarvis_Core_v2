# ISSUE 072 — Missing comparable Realtime Mini versus Full telemetry

**Version:** 0.1.2-repair6-repair4
**State:** Experimental candidate; live Windows test required.

## Root cause

Current terminal prints provider-side response output counts but omits cached,
input and model-specific token billing and cannot show which backend LLM is
selected for delegated reasoning. This prevents fair Mini-versus-Full choice.

## Corrective action

Add an opt-in-per-launch model A/B command (no file write), separate Realtime
cost estimator from OpenAI's usage records, tool/route/backend model trace,
per-turn user/model reply lengths and per-session totals. Shadow disabled.
Existing speech ownership route and tool permissions unchanged.

## Caveats

Standard prices can change; estimates are not invoices. Core/Luna provider
usage is excluded; some usage details may be absent and correctly flagged.
No test uses live cloud credentials. Verify full A/B trials on Windows.
