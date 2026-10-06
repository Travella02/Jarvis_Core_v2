# Jarvis Core v2 0.0.9 Repair2 - GPT-Live WebRTC Client Transport

## Scope

Repair2 changes the **client-device GPT-Live media transport used for live acceptance**. It does not change Jarvis Core authority, Luna routing, memory, tools, permissions, runtime state, client-delegation semantics, or the accepted local Whisper/Luna/Qwen fallback.

The existing primary-WebSocket GPT-Live lab remains available as a server/debug fallback. Repair2 adds the transport we actually want to evaluate for a user-facing desktop/mobile client: **browser WebRTC media with Jarvis Core remaining on the trusted Python side**.

## Why Repair2 exists

The first 0.0.9 WebSocket A/B runs proved the important architecture: GPT-Live can delegate meaningful work into the existing Conversation Core/Luna path. They also exposed recurring local playback pops/clicks. Repair1 improved PCM continuity, but device-backend testing still produced severe artifacts, including pitch-shifted/chipmunk playback through the WASAPI endpoint.

That made the architectural mismatch clear: the WebSocket lab was making Python manually own network PCM, resampling, jitter buffering, PortAudio scheduling, and Windows device output. For a client device, OpenAI recommends WebRTC, where microphone and generated speech use negotiated media tracks and JSON control events use a data channel.

## What changed

### Browser-owned WebRTC media

`apps/gpt_live_webrtc_lab.py` serves a loopback-only browser lab. The browser uses:

- `navigator.mediaDevices.getUserMedia()` for microphone capture;
- `RTCPeerConnection` for GPT-Live media;
- an HTML audio element for remote speech playback;
- the GPT-Live WebRTC data channel for transcript/delegation/control events.

The WebRTC session payload deliberately **omits `audio.format`**. Media format is negotiated by WebRTC instead of being pinned to the Python PCM rate.

### Trusted session broker

The OpenAI project API key never enters browser JavaScript. Python exchanges the browser SDP offer for a GPT-Live SDP answer through `POST /v1/live/sessions`, then returns only the session ID and SDP answer to the localhost page.

### Jarvis Core still owns the backend

GPT-Live remains configured for client delegation. The browser forwards Live JSON events over a localhost control socket to `BrowserWebRTCRelaySession`, which normalizes them into the same provider-neutral `VoiceFrontendEvent` contract used by the WebSocket adapter.

`LiveConversationBridge` therefore remains unchanged: transcript/delegation events enter the authoritative Conversation Core/Luna path, and verified backend commentary is returned to the browser data channel for GPT-Live to speak.

### Shared event normalization

GPT-Live JSON event conversion moved into `providers/voice_frontend/openai_live/events.py`. The WebSocket and WebRTC paths use the same event normalizer so transport choice cannot create a second conversation/delegation protocol.

### WebSocket retained

`python -m apps.gpt_live_lab ...` still exercises the server-owned raw-PCM WebSocket path. It remains useful for server-side audio, diagnostics, and fallback. It is no longer the preferred client-device acceptance transport.

## V1 lesson carried forward

The V1 master architecture explicitly separated an Electron/React WebRTC interaction layer from the Python Jarvis Core and recommended WebRTC for OpenAI realtime client audio because it handles client media more robustly than manual audio WebSockets. Repair2 carries that lesson forward without copying V1 coupling: the browser owns media while Python Core continues to own state, memory, orchestration, and backend work.

## Security boundary

Repair2 is still a **local A/B lab**. It binds only to `127.0.0.1`; remote/mobile authenticated exposure, TLS/device pairing, and a production sideband/control topology are deferred. The OpenAI project API key stays on the trusted Python side.

## Dependencies

No new Python or Node dependency is required. Repair2 uses the already-pinned FastAPI, Uvicorn, and HTTPX stack plus the browser's built-in WebRTC implementation.
