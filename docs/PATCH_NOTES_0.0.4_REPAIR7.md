# 0.0.4-repair7 - Audio Device Compatibility & Response Warmup

This repair addresses two live-acceptance failures without changing the selected providers or the ORVEX provider boundaries.

## Microphone compatibility

The first Voice Lab run silently used the OS default microphone, and explicitly selecting a HyperX endpoint failed with PortAudio `Invalid sample rate` because Voice Lab requested 16 kHz directly from every Windows endpoint.

Repair7 opens a selected microphone at its own native/default sample rate, then resamples fixed-duration mono PCM16 blocks inside the replaceable `sounddevice` integration to the 16 kHz frames required by WebRTC VAD and whisper.cpp. STT, Voice Core, Conversation Core, and Whisper remain unaware of the hardware rate.

Voice Lab now:
- shows host API and native rate for every listed audio endpoint;
- prints the exact selected input/output before listening;
- provides `--mic-test` so an endpoint can be verified without STT, Luna, or TTS cost;
- allows explicit input/output IDs to be persisted in ignored `.runtime/voice/audio_devices.json` with `--save-devices`;
- fails clearly when a selected endpoint has no input channels.

## Latency correction

The first successful turn measured about 22 seconds between Luna first text and Chatterbox first audio. The Voice Lab process had not loaded Chatterbox before the user spoke, so model construction/GPU loading was incorrectly sitting inside conversational latency.

Repair7 preloads the local STT and TTS providers before printing `Listening...`. The one-time process startup may still take noticeable time, but that time is now paid before the conversation begins and the loaded providers remain resident for the turn. Voice Lab also prints stage-to-stage timing deltas so remaining STT, Luna, and TTS inference latency can be judged separately.

This repair does not claim final full-duplex latency. Native streaming Chatterbox output, AEC, always-open microphone/barge-in, and deeper endpoint/STT optimizations remain later work if live measurements show they are needed.
