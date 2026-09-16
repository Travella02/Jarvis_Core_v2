# Jarvis Core v2

Jarvis Core v2 is a clean rebuild of Jarvis with provider-independent intelligence, an ORVEX-owned realtime voice architecture, one authoritative conversation/context system, and tool authority kept outside model providers.

## Current milestone

**0.0.3 - Conversation Core**

This milestone introduces the first authoritative `ConversationContext`, deterministic referent resolution, a Core state machine/event bus, per-turn correlation + cancellation IDs, context snapshot/restore contracts, and a typed conversation path that routes through `IntelligenceProvider` while preserving shared transcript state across turns.

The V1 regression where **"resume it"** could resume YouTube instead of the currently discussed task is now represented as a deterministic behavioral benchmark: explicit wording wins first, then conversational focus; material ambiguity returns a clarification requirement instead of guessing.

It intentionally does **not** add microphone/audio capture, VAD, STT/TTS runtime, tool execution, permissions, durable memory persistence, autonomous tasks, or desktop UI. Those remain later milestones.

## Requirements

- Python 3.11+
- Project-local `.venv` recommended
- OpenAI Python SDK 3.13.0
- A local `OPENAI_API_KEY` only for live cloud conversation tests

## Local verification

```powershell
python -m unittest discover -s tests -v
python -m core.diagnostics
python -m apps.conversation_benchmark
python -m apps.conversation_lab --context-demo
```

The benchmark/context demo use no network and perform no external actions.

## Live typed conversation

With the existing local `.env` configured:

```powershell
python -m apps.conversation_lab --turn "For this conversation, remember the test word bluejay." --turn "What test word did I ask you to remember? Reply with only the word." --reasoning quick
```

Or start the interactive development shell:

```powershell
python -m apps.conversation_lab
```

The typed lab shares one authoritative context across turns. It does not execute tools or OS/account actions.

## Canonical direction

The project-root master handoff PDF is canonical unless explicitly superseded. The V1 checkpoint under `Reference_jarvis_corev1/` is read-only behavior/code reference and must not be modified or used as the v2 foundation.
