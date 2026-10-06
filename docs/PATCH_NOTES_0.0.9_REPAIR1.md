# Jarvis Core v2 0.0.9 Repair1 — Continuous GPT-Live Audio Playback

## Scope

Repair1 is deliberately narrow. It addresses audible GPT-Live popping/clicking found during the first real 0.0.9 A/B session. It does **not** change Jarvis Core authority, Luna routing, memory, tools, permissions, delegation semantics, runtime state, or the accepted local Whisper/Qwen fallback path.

## What changed

### 24 kHz GPT-Live PCM default

The GPT-Live WebSocket frontend now defaults to mono PCM16 at **24 kHz**, matching OpenAI's default Live PCM mode. 16 kHz remains a supported explicit override.

### Continuous device-rate resampling

`SoundDeviceAudioOutput` now uses a stateful streaming PCM16 mono resampler whenever provider rate and physical output rate differ. Interpolation phase and the boundary sample survive across `AudioFrame` boundaries, so arbitrary network packetization cannot create a new resampling discontinuity at each packet.

This fix lives in the provider-neutral audio integration layer. GPT-Live, Qwen, and future providers do not contain Windows/device-rate logic.

### Live playback conditioner

`integrations/audio/streaming_pcm.py` adds a provider-neutral streaming PCM playback conditioner for full-duplex/network sources:

- arbitrary even-length PCM16 chunks are assembled into stable 20 ms source frames;
- playback starts/restarts with a 40 ms source cushion to absorb ordinary WebSocket jitter;
- a partial tail separated by a long gap is padded with silence instead of being glued to the next speech burst;
- first audio after rebuffer gets a short fade-in;
- user barge-in clears not-yet-consumed PCM and emits a 5 ms fade to zero instead of an abrupt waveform cut.

The A/B lab reports interruption fades and dropped unplayed bytes at shutdown for debugging.

## V1 lesson carried forward

V1 had no equivalent local GPT-Live/SoundDevice resampler, so no code was copied. V1 playback issues 043/046/047 did establish that remote generation/drain events and physical local playback are distinct boundaries. Repair1 follows that lesson by keeping audible continuity and drain behavior in the local playback layer.

## No new dependency

Repair1 uses only the Python standard library and the already-accepted audio/WebSocket stack.
