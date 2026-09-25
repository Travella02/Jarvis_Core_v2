# Jarvis Core v2 - Current Handoff Instructions

## Canonical source

Read `Jarvis_Core_v2_Cloud_First_Master_Handoff_2026-09-15.pdf` first. It is canonical unless the user explicitly changes a rule.

## Current candidate

**0.0.4-repair8 - Voice Lab / Realtime Response Pipeline**

Initial candidates are local whisper.cpp `large-v3-turbo-q5_0` STT and local Chatterbox Turbo TTS around the already accepted GPT-5.6 Luna intelligence path. These providers are replaceable adapters. ORVEX Core owns audio/VAD/endpointing/chunking/cancellation/telemetry.

0.0.4 is intentionally a half-duplex Voice Lab. Full duplex, AEC/noise handling, automatic acoustic barge-in, precise heard/unheard alignment, and device-recovery polish remain 0.0.5.

Repair1 pins Windows CUDA whisper.cpp builds to a compatible Visual Studio 2022/v143 instance instead of allowing CMake to auto-select an unsupported newer Visual Studio toolset. Backend-specific build trees also prevent stale CMake generator caches from poisoning retries.

Repair2 keeps that working toolchain path and replaces the fragile one-shot PowerShell model download with resumable curl retries, BITS fallback, partial-file recovery, checksum validation, and atomic final installation.

Repair3 keeps Whisper unchanged and tightens only the isolated Chatterbox runtime: PyTorch/Torchaudio 2.7.1 + cu128 for Blackwell, a CUDA smoke test, structured sidecar startup errors, and persisted stderr/tracebacks so TTS failures are diagnosable rather than opaque.

Repair4 keeps that working Blackwell runtime and moves Chatterbox Turbo model delivery under ORVEX control: setup prefetches only the runtime-required model/tokenizer assets with retry/resume, BITS fallback, weight checksums, and atomic install; the sidecar then loads the explicit local model directory with `from_local()` so provider-health/live startup no longer downloads model weights.

Repair5 fixes the PowerShell asset URL construction exposed during live testing. Asset URLs now use explicit format-string construction with escaped filenames and a pinned upstream Chatterbox Turbo revision, preventing PowerShell from interpreting `?download` as part of a variable name and eliminating the malformed 404 path while retaining repair4 retry/resume, checksums, and local-only startup.

Repair6 fixes the final local-loader API mismatch surfaced after all Chatterbox assets were installed: the pinned 0.1.7 runtime uses the two-argument Turbo `from_local()` API, while newer upstream versions add an optional Nano selector. The Turbo adapter now uses the common signature and remains independent of Nano-specific loader parameters.

Repair7 fixes the first real microphone/latency acceptance failures. PortAudio microphone endpoints are now opened at their native Windows sample rate and resampled inside the audio integration to Jarvis's provider-neutral 16 kHz PCM stream, so headsets that reject 16 kHz directly can still feed Whisper/WebRTC VAD. Voice Lab now identifies the exact selected input/output and host API, provides a no-AI mic meter, can persist explicit device choices under ignored `.runtime/`, and preloads Whisper/Chatterbox before listening so local model load time is removed from the user-response latency path.

Repair8 responds to the first valid end-to-end latency measurement (93 ms endpoint-to-STT, ~3.2 s STT-to-Luna-first-text, ~2.4 s Luna-first-text-to-TTS-audio). Luna now defaults to `none` reasoning for the fastest everyday path, voice turns receive a concise spoken-response instruction, speech chunking uses a smaller opening phrase, and model deltas -> TTS synthesis -> physical playback run as separate queued stages. Core also normalizes display markup before speech and exposes granular chunk/synthesis/playback latency marks. Future hard-task escalation should switch providers/models rather than slowing Luna by default.

## Non-negotiable direction

- Clean rebuild; V1 stays untouched as fallback/reference.
- Cloud-first and model-independent intelligence.
- GPT-5.6 Luna remains the initial everyday provider through `OpenAIProvider`.
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
