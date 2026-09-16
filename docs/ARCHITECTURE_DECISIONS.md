# Jarvis Core v2 Architecture Decisions

## Status

Canonical foundation decisions for **0.0.1 - Foundation**. The project-root master handoff PDF remains authoritative if this summary and the PDF ever conflict.

## ADR-001 — Clean rebuild; V1 stays read-only

Jarvis Core v2 is a clean repository architecture. The existing `Jarvis_Real_Time` project and supplied V1 checkpoint are fallback/reference only. Reuse must be deliberate at the behavior, test, semantic, or isolated-implementation level; V1 architecture is not copied wholesale.

## ADR-002 — Intelligence is provider-independent

Core code depends on `IntelligenceProvider`, not a provider SDK. GPT-5.6 Luna is the initial everyday cloud model planned for 0.0.2 through an `OpenAIProvider`. Stronger cloud-model escalation is policy-driven. Future local/offline intelligence is an optional provider, not a launch dependency.

Provider/model names, endpoints, context limits, pricing, snapshots, and rate limits are configuration concerns. OpenAI-specific response/tool schemas must remain inside the OpenAI adapter.

## ADR-003 — ORVEX owns realtime voice orchestration

ORVEX Core owns streaming audio flow, VAD/endpointing, interruption/barge-in, cancellation, AEC/noise handling, turn state, and STT/TTS routing. Concrete STT/TTS engines remain replaceable adapters. 0.0.1 defines only provider-neutral speech/audio contracts; realtime behavior is intentionally deferred.

## ADR-004 — Tool authority remains outside intelligence providers

A model/provider can see `ToolDefinition` metadata and propose a typed `ToolRequest`. It never receives an executor/callback or direct machine/account authority. Permission checks, confirmations, execution, verification, auditing, safe retry, and idempotency belong to Jarvis Core.

Reasoning level/model strength never changes authority.

## ADR-005 — One authoritative conversation/context system

Typed input, voice input, providers, tools, tasks, and UI will converge on one authoritative conversation/context system. Provider switching must not reset personality, memory, referents, pending approvals, or task state. The concrete `ConversationContext`, referent resolver, and event/state machine are reserved for 0.0.3.

## ADR-006 — Correlation and cancellation cross boundaries

Provider/tool/voice contracts carry opaque trace IDs and a provider-neutral cancellation token. These are primitives only; 0.0.1 does not implement conversation lifecycle semantics.

## ADR-007 — Foundation has no runtime provider dependencies

0.0.1 uses the Python standard library only. It performs no model requests, audio capture, OS actions, account actions, or network calls. This makes architecture coupling visible before provider/runtime work begins.

## ADR-008 — Acceptance gates normal version advancement

Every candidate follows patch ZIP → root-safe apply → automated tests → focused live acceptance → same-version repair suffix if needed → exact cleanup → final verification → one focused commit. The next normal version does not begin until acceptance/commit unless explicitly overridden by Tanner.

## ADR-009 — OpenAI is an adapter, not Jarvis Core

0.0.2 implements `OpenAIProvider` under `providers/intelligence/openai/`. OpenAI SDK imports and Responses API schemas are allowed only inside that adapter package. `core/`, integrations, backend, and apps consume provider-neutral contracts or the provider class itself; they do not import the OpenAI SDK.

The initial development default is `gpt-5.6-luna`, but the model ID is provider configuration rather than a Core constant. A future cloud provider or `LocalProvider` must be able to satisfy the same `IntelligenceProvider` contract without rewriting conversation state, tools, permissions, or voice.

## ADR-010 — Responses streaming is the 0.0.2 provider path

`OpenAIProvider` uses the Responses API with streaming enabled. Provider-specific text delta, completion, error, and function-call events are translated into `IntelligenceEvent` values. Function calls become typed, non-executable `ToolRequest` intent objects; they are never invoked by the provider.

Responses are sent with `store=False` in 0.0.2. The candidate also applies a configurable 4096-token request output cap for development safety while retaining the model's actual context/output capabilities in provider metadata.

## ADR-011 — Reasoning names remain provider-neutral at the Core boundary

Core sends `ReasoningPolicy` names such as `quick`, `standard`, `high`, and `extreme`. The OpenAI adapter maps these to provider-specific reasoning effort values. Full policy routing, escalation, usage budgets, and fallback remain reserved for 0.0.6.

## ADR-012 — Provider promotion requires a Jarvis benchmark

0.0.2 seeds a provider-neutral benchmark harness and corpus. It includes an exact streaming smoke case, a provider function-call case, and the V1 natural-phrasing regression **“Can you open a new tab, please?”**. Later milestones expand the same harness with context/referent resolution, permissions, recovery, latency, interruption, and capability parity cases.

## ADR-013 — SDK version is pinned per accepted candidate

The 0.0.2 candidate pins the OpenAI Python SDK to `3.13.0` in project dependency configuration. SDK upgrades are explicit project changes with tests, rather than silent environment drift.

## ADR-014 — 0.0.2 cancellation is cooperative stream cancellation, not a remote-inference guarantee

**Decision:** `IntelligenceProvider.cancel(request_id)` in 0.0.2 must immediately stop provider output from reaching Core, close the foreground stream, and emit `CANCELLED`. The OpenAI adapter does not claim that closing a foreground SSE stream is equivalent to the background Responses cancellation endpoint.

**Why:** the provider abstraction needs cancellation now, while the realtime voice milestone will require measured barge-in latency/cost behavior and may justify a different transport. Faking stronger semantics now would be worse than recording the boundary explicitly.

**Consequence:** 0.0.4 must include a live cancellation/interrupt benchmark before choosing the long-term cloud transport for voice-driven turns.
