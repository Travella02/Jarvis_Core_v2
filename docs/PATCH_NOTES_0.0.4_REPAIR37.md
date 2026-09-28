# Jarvis Core v2 0.0.4 Repair37 — Clean Alternating Luna Model A/B Probe

Repair36 fixed the real WebSocket continuation bug. The old latency probe still
made two different live API requests per round ("raw" then Conversation Core),
so subtracting them looked like app overhead even though server/network variance
could dominate the difference.

Repair37 is benchmark-only. It changes no production Jarvis runtime behavior.

## New probe

`apps.luna_model_ab_probe`

It creates one persistent OpenAI provider + Conversation Core stack per model.
Each stack receives one discarded warmup request, then measured requests alternate
wall-clock order:

- pair 1: model A -> model B
- pair 2: model B -> model A
- pair 3: model A -> model B
- ...

This reduces time-of-test bias while preserving an independent continuation
chain for each model.

Only the real Conversation Core voice path is measured.

## Per sample

The probe records:
- Conversation Core TTFT
- Conversation Core total time
- response.created timing
- response.in_progress timing
- provider first-text timing
- response terminal timing
- continuation status/reason
- connection reuse
- input item count
- actual service tier

## Summary

For each model it prints:
- mean TTFT
- median TTFT
- p90 TTFT
- min/max TTFT
- mean/median/p90 total time
- provider first-text distribution
- continuation-health count

Standard processing (`service_tier=default`) is the default. Fast mode remains
explicit opt-in only.
