# Jarvis Core v2

Jarvis Core v2 is a clean rebuild of Jarvis with provider-independent intelligence, an ORVEX-owned realtime voice architecture, one authoritative conversation/context system, and tool authority kept outside model providers.

## Current milestone

**0.0.4-repair18 - Voice Lab / Luna + Qwen Latency Pass**

This milestone begins the local-first ORVEX Voice Engine on top of the accepted 0.0.3 Conversation Core.

Initial candidate path:

`microphone -> ORVEX input validation / endpointing -> whisper.cpp large-v3-turbo-q5_0 -> Conversation Core -> GPT-5.6 Luna -> swappable local TTS (Chatterbox Turbo or Qwen3-TTS 0.6B Base) -> speakers`

Luna now defaults to its fastest `none` reasoning mode for ordinary Jarvis turns; future difficult-task escalation should switch providers rather than making the everyday Luna path slower.

Whisper and Chatterbox are adapters, not Core dependencies. Model/provider-specific runtimes live under ignored `.runtime/voice/` folders and can be replaced without rewriting Conversation Core or the ORVEX audio/endpoint/cancellation layer.

0.0.4 is intentionally a half-duplex development lab: it endpoints one utterance and then speaks the response. Full-duplex mic + speaker operation, AEC/noise handling, automatic barge-in, and precise heard/unheard response alignment remain 0.0.5.

## Requirements

- Python 3.11+ (the project development baseline remains Python 3.11)
- Project-local `.venv`
- OpenAI Python SDK 3.13.0
- `sounddevice==0.5.6`
- `webrtcvad-wheels==2.0.14`
- OpenAI API key in local `.env` for Luna
- For GPU whisper.cpp: Git, CMake, and a current NVIDIA CUDA Toolkit
- Chatterbox and Qwen3-TTS use separate private virtual environments created by their setup scripts

## Local verification

```powershell
python -m unittest discover -s tests -v
python -m core.diagnostics
python -m apps.voice_benchmark
python -m apps.voice_lab --doctor
```

These commands do not capture microphone audio or make a live Luna request. `--doctor` does not load the local models.

## Voice runtime setup

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_whisper_cpp.ps1 -Backend cuda
powershell -ExecutionPolicy Bypass -File .\scripts\setup_chatterbox_runtime.ps1 -Profile modern-cuda
powershell -ExecutionPolicy Bypass -File .\scripts\setup_qwen3_tts_runtime.ps1 -Profile modern-cuda
python -m apps.voice_lab --provider-health
python -m apps.voice_lab --devices
python -m apps.voice_lab
```

Optional Chatterbox reference voice test:

```powershell
python -m apps.voice_lab --voice-ref "C:\path\to\consented_reference.wav"
```

## Canonical direction

The project-root master handoff PDF is canonical unless explicitly superseded. The V1 checkpoint under `Reference_jarvis_corev1/` is read-only behavior/code reference and must not be modified or used as the v2 foundation.

### 0.0.4-repair9 candidate
Voice Lab now favors complete-sentence TTS chunks and can run multiple warm turns with `python -m apps.voice_lab --turns 3` for realistic latency/prosody testing.

### 0.0.4-repair10 candidate
WebRTC VAD is no longer sufficient by itself to create a user turn. ORVEX now requires independent speech-energy/duration evidence before any candidate audio reaches STT. Use `python -m apps.voice_lab --audio-diagnostic` to capture/listen to native device audio, Jarvis 16 kHz resampling, and the exact evidence-approved Whisper input.


### 0.0.4-repair11 candidate
Qwen3-TTS 12Hz 0.6B Base is available as a parallel local A/B TTS adapter. Chatterbox remains the default candidate. Select Qwen with `--tts-provider qwen3`; the Base clone model also requires `--voice-ref` and should use `--voice-ref-text` for the strongest cloning test.

The official desktop Qwen Python runtime is not treated as the mobile runtime. Phone deployment remains a separate provider/runtime decision behind the same `TextToSpeechProvider` contract, with native/quantized Qwen or a lighter local provider to be benchmarked later.

## Local voice reference library

Voice Lab can now keep multiple named voice identities under ignored runtime user data instead of requiring raw file paths every run. Initialize/list the library with:

```powershell
python -m apps.voice_lab --voice-library
```

Save a clean reference clip as a reusable profile:

```powershell
python -m apps.voice_lab --save-voice-profile "Qwen Test Voice" --tts-provider qwen3 --voice-ref "C:\path\to\reference.wav" --voice-ref-text "Exact transcript of the clip." --voice-language English
```

Then run it by ID:

```powershell
python -m apps.voice_lab --turns 3 --tts-provider qwen3 --voice-profile qwen-test-voice
```

Each profile can hold multiple reference clips and one primary reference. Personal audio remains under `.runtime/voice/references/` and is not committed to Git.

### 0.0.4-repair13 Voice Lab note
Voice onset is now redundant: WebRTC VAD remains the primary fast signal, while ORVEX acoustic activity recovery can rescue strong real speech when VAD misses it. Raw VAD evidence remains separately observable; quiet noise is still rejected before STT.


### 0.0.4-repair14 Voice Lab note
Qwen synthesis now follows the official float-waveform -> libsndfile WAV path instead of provider-specific manual PCM scaling. Speaker playback adapts mono PCM16 TTS frames to the selected physical output device's native sample rate inside the audio integration layer, while PlaybackLedger accounting remains expressed in provider/source bytes. Use `--tts-diagnostic` to save the exact provider PCM stream to a WAV without PortAudio playback; this cleanly separates model/waveform problems from speaker-device problems.


### 0.0.4-repair16 Qwen clone diagnostic

Use the provider-specific direct diagnostic before making more Qwen playback changes:

```powershell
python -m apps.voice_lab --qwen-clone-diagnostic --voice-profile tanner-test
```

It validates the saved reference and compares Qwen's direct full-reference and x-vector-only Base clone paths. The official Jarvis default voice is now treated architecturally as a versioned ORVEX brand identity above the concrete TTS provider; alternate and user-cloned voices remain optional profiles.

### 0.0.4-repair17 Qwen stable clone mode

Repair16 live testing proved Qwen's x-vector-only clone path works with the saved reference while the transcript-conditioned full-reference path can run away into invalid long-form audio. Normal Qwen voice profiles now default to x-vector cloning even when a reference transcript is stored. The transcript-conditioned path remains available only through the provider-specific diagnostic until it passes separate acceptance.

### 0.0.4-repair18 Luna + Qwen latency pass

Repair18 keeps Luna on `reasoning=none` and tightens the spoken path without changing the model/provider boundary:

- voice-only Luna responses use a 256-token output cap by default while typed/non-voice requests keep the general 4096-token development cap;
- GPT-5.6 voice turns enable implicit 30-minute prompt caching when the visible prefix becomes cacheable;
- `JARVIS_OPENAI_SERVICE_TIER` is provider-owned and defaults to `auto`; `fast` can be A/B tested explicitly because it may cost more;
- Voice Lab performs a tiny hidden Luna request before listening so HTTP/TLS cold-start latency is moved out of the first user turn;
- Voice Lab performs one hidden local TTS synthesis before listening so Qwen/Chatterbox inference kernels and cloned-voice prompt caches are warm;
- Qwen's normal Jarvis phrase budget is reduced from 8192 to 512 codec tokens, which remains far above the duration needed for a short spoken phrase but avoids an oversized generation budget.

Use the dedicated live probe to separate raw API latency from Jarvis/Conversation Core overhead:

```powershell
python -m apps.luna_latency_probe --rounds 4
```

Optionally compare OpenAI Fast mode without changing the default:

```powershell
python -m apps.luna_latency_probe --rounds 4 --service-tier fast
```

Then run the normal multi-turn Qwen session and compare turns 2+ after both providers are warm.

### 0.0.4-repair19 latency experiment

Voice Lab can now A/B Luna over a persistent Responses WebSocket (`--luna-transport websocket`, the Voice Lab default) versus the existing HTTP path (`--luna-transport http`). Provider continuation is validated against Conversation Core before incremental input is used. Whisper and TTS are prewarmed before listening, and the first TTS unit may use a bounded natural comma-clause to reduce time-to-first-audio without returning to arbitrary mid-sentence cuts.


## 0.0.4-repair20 — Whisper Warmup Runtime Fix
Repair20 fixes the hidden first-turn Whisper inference warmup introduced in repair19 by restoring the missing `CorrelationContext` import and adding executable regression coverage for that path.
