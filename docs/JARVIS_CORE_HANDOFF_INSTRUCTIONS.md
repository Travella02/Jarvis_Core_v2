# Jarvis Core v2 - Current Handoff Instructions

## Canonical source

Read `Jarvis_Core_v2_Cloud_First_Master_Handoff_2026-09-15.pdf` first. It is canonical unless the user explicitly changes a rule.

## Current candidate

**0.0.8 - Client Input & Runtime Control**

0.0.5 Realtime Conversation Control, 0.0.6 Runtime State & Event Foundation, and 0.0.7 Portable Runtime API & Client Reconnection are accepted. 0.0.8 completes the first two-way client boundary without creating a second conversation owner.

Required 0.0.8 behavior:
- Typed client input enters the existing `ConversationCore`; the Runtime API never creates a parallel transcript, provider session, or client-owned state machine.
- Clients submit `runtime_id`, `conversation_id`, `client_request_id`, `client_id`, and text. Core/runtime generate correlation/request/turn/cancellation IDs; clients may observe but never choose those IDs.
- `client_request_id` is runtime-scoped transport idempotency. Retrying the same accepted request returns the same command/trace and must not execute the provider twice. Rebinding the same request ID to different input is rejected.
- Stale `runtime_id` or `conversation_id` is rejected before execution so an uncertain retry cannot land in a restarted runtime or replacement conversation.
- A client may cancel the active command it submitted through Conversation Core's existing cooperative cancellation path. It may not directly mutate Core state.
- Results remain authoritative Core/runtime events and can be replayed through the existing event cursor contract after reconnect.
- A second client command is rejected while a foreground turn is already active; 0.0.8 does not introduce a hidden command queue.
- The protocol remains platform-neutral and loopback-only. Remote device pairing/authentication/TLS/cloud relay remain deferred.
- The accepted voice path remains unchanged.

Reference-project lessons applied before implementation:
- V1 ISSUE-075: transport idempotency and UI/domain deduplication are different concerns; one client request ID must prevent duplicate execution without collapsing genuine later utterances.
- V1 ISSUE-117 and ISSUE-205: each completed turn needs one response owner; duplicate provider/client events must reuse the in-flight transaction rather than create a competing response path.
- V1 ISSUE-172: cancellation is a distinct control path and must never be interpreted as positive confirmation/execution.
- V1 ISSUE-310: clients are not authority for server-owned execution policy. 0.0.8 applies that principle locally by keeping trace/state authority in Core.
- 0.0.7 reconnect rules remain in force: `runtime_id + event cursor` governs replay and clients never reconstruct Jarvis truth from local UI state.

Known 0.0.8 limitations: the API remains loopback-only; idempotency history is in-memory and scoped to one runtime lifetime; there is no durable command queue; clients cannot remotely pair/authenticate yet; production desktop/mobile UI, tools, permissions, Memory 2.0, autonomous work, and fuzzy wake-word variants remain deferred.

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
