# Jarvis Core v2 — Current Handoff Instructions

## Canonical source

Read `Jarvis_Core_v2_Cloud_First_Master_Handoff_2026-09-15.pdf` first. It is canonical unless the user explicitly changes a rule.

## Current candidate

**0.0.2 - Intelligence Provider**

Scope: real `OpenAIProvider` behind the provider-neutral `IntelligenceProvider`, GPT-5.6 Luna as the initial default, foreground streaming, non-executable tool-call translation, cooperative cancellation, provider health/configuration, and a seed benchmark/live intelligence lab. No conversation core, voice runtime, permissions executor, memory, or desktop UI yet.

## Non-negotiable direction

- Clean rebuild; V1 stays untouched as fallback/reference.
- Cloud-first and model-independent intelligence.
- GPT-5.6 Luna is the initial everyday model through `OpenAIProvider`.
- Stronger cloud-model escalation is policy-driven and arrives later.
- Local LLM support is future optional/private/offline capability, not a launch dependency.
- ORVEX owns realtime voice orchestration; STT/TTS engines are replaceable providers.
- Voice and typed input must eventually share one conversation/context truth.
- Models can request tools but never own permissions or direct execution authority.
- Reasoning level never changes permissions.

## Required patch workflow

1. Deliver `Jarvis_Core_v2_<version>_patch.zip`.
2. Extract it into the existing project root.
3. Activate the project `.venv`.
4. Run `python apply_<version>_patch.py` from the project root.
5. Install/update only the dependency set explicitly required by that candidate.
6. Run `python -m unittest discover -s tests -v`.
7. Run focused commands in `docs/TESTING_GUIDE_<version>.md`.
8. The user performs live/manual acceptance.
9. On failure, stay on the same candidate using `repair1`, `repair2`, etc.
10. Only after acceptance, remove the exact patch/apply/backup artifacts, verify status, rerun tests, and create one focused commit.

Never use broad cleanup commands. Never commit `.env`, secrets, databases, `.venv`, `node_modules`, model weights, patch ZIPs, `patch_files/`, apply scripts, or installer backup folders.

## Version sequence

`0.0.1 → 0.0.2 → ... → 0.0.9 → 0.1.0`

Do not begin the next normal version until the current candidate is accepted and committed unless the user explicitly overrides that rule.
