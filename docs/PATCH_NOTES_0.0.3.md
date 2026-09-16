# 0.0.3 - Conversation Core

## Added

- Authoritative `ConversationContext` with typed transcript and referent slots from the master handoff.
- Serializable context snapshot/restore contract for future persistence/restart work.
- Deterministic `ReferentResolver` with explicit wording/focus precedence and ambiguity-safe behavior.
- Canonical Core state machine and structured in-process event bus.
- Correlation/request/turn/cancellation ID creation owned by Conversation Core.
- `CancellationRegistry` for exact active-turn cancellation targeting.
- Provider-independent `ConversationCore.submit_typed()` path with shared history across turns.
- Partial/complete/interrupted response exposure tracking.
- Tool requests remain typed intent only; they do not become executed actions or active referents.
- Deterministic Conversation Core benchmark and V1 `resume it` regression case.
- Live typed Conversation Lab that can run multiple Luna turns through one shared context.

## Deliberately deferred

- Voice/audio device layer, VAD, streaming STT/TTS, endpointing, AEC, barge-in.
- Permission engine and tool executor.
- Durable task/job implementation.
- Memory database and automatic long-term context persistence.
- Desktop UI and restart restoration wiring.
- Reasoning/usage router and stronger-model escalation.
