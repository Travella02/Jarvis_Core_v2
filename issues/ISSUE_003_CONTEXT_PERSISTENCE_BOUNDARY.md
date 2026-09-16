# ISSUE-003 - Context persistence/restart boundary remains unwired

## Status

Open / explicitly deferred beyond 0.0.3.

## Why this is recorded

The master handoff requires authoritative conversation context to survive voice/typed switching, provider switching, task transitions, and eventually UI restart. 0.0.3 establishes one serializable `ConversationContext` and proves provider-independent shared context in-process, but it intentionally does not write conversation state to a durable database or automatically restore it after process restart.

## Current protection

- `ConversationContext.to_dict()` / `from_dict()` round-trip the authoritative working state.
- Providers receive snapshots and cannot own context.
- Tests prove referents/transcript survive serialization round-trip.

## Future acceptance requirement

Before public launch, the desktop/backend persistence owner must define crash-safe storage/restoration and tests proving an approved context snapshot survives a normal UI/Core restart without resurrecting cancelled turns, stale approvals, or stale pending tool plans.
