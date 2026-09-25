# 0.0.4 - Voice Lab

This candidate begins the ORVEX-owned local realtime voice engine.

Initial candidates:
- STT: whisper.cpp `large-v3-turbo-q5_0` (local)
- Intelligence: existing GPT-5.6 Luna provider (cloud)
- TTS: Chatterbox Turbo (local, isolated sidecar)

Included in this milestone:
- provider-neutral audio frames/devices
- local microphone/speaker integration
- WebRTC VAD adapter
- ORVEX endpoint detector with pre-roll
- streaming/partial STT adapter boundary
- response phrase chunking into local TTS
- latency telemetry and minimal playback ledger
- interruption/cancellation skeleton
- live Voice Lab and deterministic benchmark
- provider-specific runtime setup scripts

Explicitly deferred to 0.0.5:
- full duplex microphone capture while TTS is playing
- AEC/noise suppression production path
- automatic acoustic barge-in
- precise generated/synthesized/heard text alignment
- recovery from live device changes
