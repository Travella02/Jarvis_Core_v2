# 0.1.2 — Intelligence Router & Core Delegation Orchestrator

## Purpose

Move backend provider/capability selection behind authoritative Jarvis Core so the current Realtime Mini frontend can be replaced without moving routing authority into the voice provider.

## What changed

- Added provider-neutral `DelegationRequest`, `DelegationDecision`, `DelegationResult`, and `DelegationOrchestrator` contracts under `core/intelligence/`.
- Realtime continues to describe the delegated goal plus a coarse capability category only. It never names or selects a backend model/provider.
- Conversation Core now supports a per-turn provider override used only by trusted in-process delegation orchestration. The configured default provider remains unchanged.
- Optional `strong` provider registration is composed in the desktop host from `JARVIS_OPENAI_STRONG_MODEL`; leaving it blank keeps all delegated reasoning on the default provider.
- Routine delegated reasoning stays on the default route. Harder delegated reasoning may use the configured strong route after Core's local routing policy reaches its threshold.
- Durable memory, actions, current-data lookups, and long-running background tasks are explicit capability slots. Until their authoritative handlers exist, they return `unavailable` rather than silently falling through to a model.
- Realtime function results now include route metadata for diagnostics while the frontend still receives only authoritative Core results.

## V1 lessons applied

- A positive route may not silently fall through into another capability after failure.
- Tool/model/provider routing belongs to Core rather than presentation/client layers.
- Unsupported operations must fail truthfully instead of letting the conversational model infer success.
- Provider routes remain replaceable configuration rather than hard-coded product identity.

## Deliberate limitations

0.1.2 is routing/orchestration foundation, not Memory 2.0, Tool execution, current-data browsing, or durable background tasks. Those capabilities now have explicit registration points but are not falsely implemented.

The first strong-route policy is intentionally deterministic and local to avoid adding a second classifier-model call to every delegation. It should be replaced or refined only after real routing telemetry demonstrates a better policy.
