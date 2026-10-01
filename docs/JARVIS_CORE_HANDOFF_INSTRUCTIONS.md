# Jarvis Core v2 - Current Handoff Instructions

## Canonical source

Read `Jarvis_Core_v2_Cloud_First_Master_Handoff_2026-09-15.pdf` first. It is canonical unless the user explicitly changes a rule.

## Current candidate

**0.0.5 - Realtime Conversation Control**

0.0.4 is accepted and committed. Its final voice path uses local whisper.cpp `large-v3-turbo-q5_0`, GPT-6 Luna at `reasoning=none` on Standard processing, persistent Responses WebSocket continuation, and whole-response local Qwen3-TTS with fixed-seed consistency.

0.0.5 is intentionally limited to **wake, sleep, continuous conversation, and interruption**. Do not add tools, memory, UI, working/researching/error modes, or other product state here. Lifecycle presence is separate from later activity/status state.

Required behavior:
- Starts sleeping by default.
- Sleeping speech stays local unless an utterance begins with a configured wake phrase.
- Full-sentence wake commands are preserved: `Hey Jarvis, what are the latest updates in Rocket League?` wakes Jarvis and routes the command remainder immediately.
- Once awake, conversation continues without repeating the wake phrase.
- Explicit sleep phrases return Jarvis to sleep.
- 60 seconds of true inactivity after the latest user/Jarvis activity also returns Jarvis to sleep.
- While Jarvis speaks, the microphone is active. Endpoint-confirmed new user speech stops playback immediately and becomes the next turn.
- Barge-in never discards conversational meaning. Core retains generated assistant text, records the physical playback offset and approximate heard prefix, and passes that interruption context to the next GPT-6 Luna turn. Provider continuation remains valid when the transcript chain matches.
- Wake phrases are configurable through environment/Voice Lab settings; `jarvis` and `hey jarvis` are defaults only.

Known 0.0.5 limitation: no production AEC yet. Headsets are the expected live-acceptance path; speakers may feed Jarvis audio back into the microphone. Exact word/audio alignment is also deferred; 0.0.5 records exact PCM playback duration plus an honest approximate heard-text prefix.

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
