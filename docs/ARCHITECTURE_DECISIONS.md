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
