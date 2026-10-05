# Jarvis Core v2 - Current Handoff Instructions

## Canonical source

Read `Jarvis_Core_v2_Cloud_First_Master_Handoff_2026-09-15.pdf` first. It is canonical unless the user explicitly changes a rule.

## Current candidate

**0.0.6 - Runtime State & Event Foundation**

0.0.5 Realtime Conversation Control is accepted. Its final path uses local Silero speech presence + whisper.cpp STT, GPT-6 Luna at `reasoning=none` / standard service tier over persistent Responses WebSocket continuation, and whole-response local Qwen3-TTS with multi-signal speech confidence. Wake/sleep, full-sentence wake commands, continuous conversation, interruption context, explicit sleep, and 60-second inactivity sleep passed live acceptance.

0.0.6 moves that accepted conversation path under `JarvisRuntime` and adds the Core runtime spine without adding tools, memory, UI, autonomous work, or new product activity modes.

Required 0.0.6 behavior:
- Runtime lifecycle is explicit and idempotent: stopped -> starting -> running -> stopping -> stopped.
- Runtime lifecycle, component/provider health, voice presence, and Conversation Core activity remain separate axes.
- One shared EventBus receives monotonic sequence numbers and supports reconnect replay after a cursor.
- A stale reconnect cursor reports a history gap instead of silently losing events.
- Correlation IDs can replay one turn's event trace.
- Runtime snapshots expose only non-secret orchestration settings and composed state.
- Intelligence provider routes are explicit; no automatic cost-changing model/service-tier fallback is enabled.
- Provider health probes are concurrent and timeout-bounded.
- Voice Lab creates Conversation Core through JarvisRuntime while preserving accepted 0.0.5 voice behavior.
- `python -m apps.runtime_lab` proves lifecycle, health, Conversation Core, reconnect replay, and trace replay without network/audio.

Reference-project lessons applied before implementation:
- do not recreate V1's single CoreState that mixed presence, foreground activity, execution/background work, degraded health, and error;
- do not map raw provider/client transport events directly into authoritative conversation state;
- do not add a durable event journal before a redacted persistence boundary exists;
- do not let slow health/status work block the realtime path;
- do not let tests silently inherit private `.env` values.

Known 0.0.6 limitations: reconnect is currently an in-process snapshot/event contract, not a network API; event replay does not survive process restart; automatic provider escalation/fallback is deferred; fuzzy wake-word variants such as `Jervis` -> `Jarvis` remain later polish.

## Non-negotiable direction

- Clean rebuild; V1 stays untouched as fallback/reference.
- Cloud-first and model-independent intelligence.
- GPT-6 Luna is the accepted everyday provider through `OpenAIProvider`, with exact model ID configurable.
- Voice and typed input share the same Conversation Core/context truth.
- STT/TTS implementations never leak into Conversation Core.
- Heavy local model/runtime files stay in ignored provider-specific `.runtime/` paths.
- Models can request tools but never own permissions or direct execution authority.
- Reasoning level never changes permissions.
- User-visible voice quality packages may be recommended by hardware later, but model choice remains replaceable and user-overridable.

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

Never commit `.env`, secrets, databases, `.venv`, `.runtime`, `node_modules`, model weights, patch ZIPs, `patch_files/`, apply scripts, or installer backup folders.

## Version sequence

`0.0.1 -> 0.0.2 -> 0.0.3 -> ... -> 0.0.9 -> 0.1.0`

### 0.0.4-repair9 live note
Repair8 reached 5,047 ms speech-end -> first-audible on the RTX 5080 laptop, with 78 ms endpoint->STT, 2,984 ms STT->Luna first text, 110 ms Luna->first speech chunk, 1,812 ms TTS request->waveform, and 63 ms waveform->audio. Repair9 removes mid-sentence TTS cuts and adds warm multi-turn testing before any provider replacement decision.

### 0.0.4 repair12 note
Voice Lab has a provider-neutral multi-voice reference library under `.runtime/voice/references/`. Use `--voice-library`, `--save-voice-profile`, and `--voice-profile`; never commit personal reference audio.
