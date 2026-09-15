# Jarvis Core v2 — Current Handoff Instructions

## Canonical source

Read `Jarvis_Core_v2_Cloud_First_Master_Handoff_2026-09-15.pdf` first. It is canonical unless Tanner explicitly changes a rule.

## Current candidate

**0.0.1 - Foundation**

Scope: repository/docs/tests/issues structure; provider-neutral intelligence/tool/voice contracts; V1 fallback inventory; local-only diagnostic path. No cloud model connection, no audio runtime, and no real tool execution.

## Non-negotiable direction

- Clean rebuild; V1 stays untouched as fallback/reference.
- Cloud-first and model-independent intelligence.
- GPT-5.6 Luna is planned as the initial everyday model through `OpenAIProvider` in 0.0.2.
- Stronger cloud-model escalation is policy-driven.
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
5. Run `python -m unittest discover -s tests -v`.
6. Run focused commands in `docs/TESTING_GUIDE_<version>.md`.
7. Tanner performs live/manual acceptance.
8. On failure, stay on the same candidate using `repair1`, `repair2`, etc.
9. Only after acceptance, remove the exact patch/apply/backup artifacts, verify status, rerun tests, and create one focused commit.

Never use broad cleanup commands. Never commit `.env`, secrets, databases, `.venv`, `node_modules`, model weights, patch ZIPs, `patch_files/`, apply scripts, or installer backup folders.

## Version sequence

`0.0.1 → 0.0.2 → ... → 0.0.9 → 0.1.0`

Do not begin the next normal version until the current candidate is accepted and committed unless Tanner explicitly overrides that rule.
