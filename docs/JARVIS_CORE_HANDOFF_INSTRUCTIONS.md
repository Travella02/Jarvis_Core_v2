# Jarvis Core v2 - Current Handoff Instructions

## Canonical source

Read `Jarvis_Core_v2_Cloud_First_Master_Handoff_2026-09-15.pdf` first. It is canonical unless the user explicitly changes a rule.

## Current candidate

**0.0.7 - Portable Runtime API & Client Reconnection**

0.0.5 Realtime Conversation Control is accepted. 0.0.6 Runtime State & Event Foundation is accepted after automated/runtime/Voice Lab regression. 0.0.7 turns the 0.0.6 snapshot/cursor contract into a real local HTTP/WebSocket client boundary without transferring state authority to the UI.

Required 0.0.7 behavior:
- The public protocol is versioned JSON over standard HTTP/WebSocket, with no Electron, Windows IPC, Python-pickle, or provider-transport coupling.
- Windows, macOS, Linux, iOS, and Android clients can consume the same protocol contract. Platform metadata is informational only and never security authority.
- `JarvisRuntime` and its existing Conversation Core remain authoritative and outlive client disconnect/restart.
- Reconnect uses `runtime_id + event sequence`; a nonzero cursor without its runtime identity cannot silently resume.
- Runtime restart, cursor-ahead, history-gap, replay-limit, and client-backpressure conditions explicitly require snapshot resynchronization.
- Event streaming subscribes before snapshot capture so no event can be lost in a snapshot/subscription race.
- Slow client queues are detected; events are never silently dropped while a connection is considered synchronized.
- The local API is loopback-only in 0.0.7. LAN/WAN exposure remains disabled until authenticated device pairing/TLS or secure relay transport exists.
- FastAPI, Uvicorn, HTTPX, and WebSockets are direct pinned dependencies rather than accidental/transitive runtime assumptions.
- `python -m apps.runtime_api_lab` proves a real TCP/HTTP/WebSocket disconnect/reconnect while the same Runtime and Conversation Core continue running.
- The accepted Voice Lab behavior remains unchanged.

Reference-project lessons applied before implementation:
- V1 ISSUE-312: preserve one Core owner; a server/client adapter must not double-start Core or enter a port restart loop;
- V1 ISSUE-280: reconnect must not depend only on one in-memory client timer;
- V1 ISSUE-300: HTTP health does not prove WebSocket runtime dependencies are installed, so WebSocket dependencies/tests are explicit;
- V1 ISSUE-007: validate provider-independent/API contracts at the local boundary;
- V1 ISSUE-033: tests/settings do not silently inherit private `.env`;
- V1 ISSUE-307: cross-device authority cannot trust client clocks/claims; runtime identity and later authenticated account/device authority are required.

Known 0.0.7 limitations: the API is loopback-only and does not yet provide remote phone-to-desktop transport; device pairing/authentication/cloud relay are deferred; replay is memory-only and does not survive Core process restart; typed-command submission through the API is deferred; fuzzy wake-word variants such as `Jervis` -> `Jarvis` remain later polish.

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
