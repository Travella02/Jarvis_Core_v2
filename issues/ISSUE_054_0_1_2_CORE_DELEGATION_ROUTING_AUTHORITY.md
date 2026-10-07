# ISSUE 054 — Core Delegation Routing Authority

## Problem

The Realtime Core bridge delegated every backend request into the same Conversation Core provider regardless of the requested capability. This preserved Core authority but did not yet provide a real model/capability routing boundary. It also risked allowing future action/memory/task requests to fall through to a language model before their authoritative executors existed.

## Resolution

0.1.2 adds a provider-neutral delegation orchestrator inside Core. Realtime supplies only the goal and coarse capability category. Core selects a provider route for reasoning or an authoritative capability handler for memory/actions/current-data/tasks.

Unsupported capabilities fail closed. A model response is never treated as proof that an action, memory lookup, current-data lookup, or background task occurred.

Provider selection is per-turn and does not mutate the conversation's configured default provider.

## Follow-up

- Register Memory 2.0 handler when its durable source of truth exists.
- Register permissioned tool/action handlers only after executor + confirmation boundaries exist.
- Register current-data/search providers behind a Core-owned data capability.
- Register durable task worker after task persistence/cancellation are implemented.
- Replace/refine deterministic complexity routing only when telemetry justifies another policy.
