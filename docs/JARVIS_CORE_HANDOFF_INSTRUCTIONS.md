# Jarvis Core v2 - Current Handoff Instructions

## Canonical source

Read `Jarvis_Core_v2_Cloud_First_Master_Handoff_2026-09-15.pdf` first. It is canonical unless the user explicitly changes a rule.

## Current candidate

**0.0.3 - Conversation Core**

Scope: one authoritative `ConversationContext`, deterministic referent resolution, canonical state machine/event bus, correlation/request/turn/cancellation IDs, context snapshot contract, and a provider-independent typed path with shared multi-turn history. No voice runtime, permission/tool execution, memory database, autonomous tasks, or desktop UI yet.

## Key 0.0.3 rule

Explicit wording outranks conversational focus; conversational focus outranks stale subsystem state. If material ambiguity remains, return a clarification requirement instead of guessing. The V1 `resume it` task-vs-YouTube regression is a required benchmark case.

## Non-negotiable direction

- Clean rebuild; V1 stays untouched as fallback/reference.
- Cloud-first and model-independent intelligence.
- GPT-5.6 Luna remains the initial everyday provider through `OpenAIProvider`.
- ORVEX owns realtime voice orchestration; voice starts in 0.0.4.
- Voice and typed input must share this same Conversation Core/context truth.
- Models can request tools but never own permissions or direct execution authority.
- Reasoning level never changes permissions.

## Required patch workflow

1. Deliver `Jarvis_Core_v2_<version>_patch.zip`.
2. Extract it into the existing project root.
3. Activate the project `.venv`.
4. Run `python apply_<version>_patch.py` from the project root.
5. Install/update only dependencies explicitly required by the candidate.
6. Run `python -m unittest discover -s tests -v`.
7. Run focused commands in `docs/TESTING_GUIDE_<version>.md`.
8. The user performs live/manual acceptance.
9. On failure, stay on the same candidate using `repair1`, `repair2`, etc.
10. Only after acceptance, remove exact patch/apply/backup artifacts, verify status, rerun tests, and create one focused commit.

Never commit `.env`, secrets, databases, `.venv`, `node_modules`, model weights, patch ZIPs, `patch_files/`, apply scripts, or installer backup folders.

## Version sequence

`0.0.1 -> 0.0.2 -> 0.0.3 -> ... -> 0.0.9 -> 0.1.0`
