# ISSUE 043 - 0.0.9 client audio transport should use WebRTC

## Status

Repair2 candidate - pending live acceptance.

## Symptom

The first real GPT-Live WebSocket A/B sessions proved client delegation but produced recurring audible pops/clicks through the Python PCM playback path. Repair1 improved packet continuity. Switching the same local pipeline from the MME output endpoint to the HyperX WASAPI endpoint then produced severe pitch-shifted/chipmunk playback and worse popping.

## Root architectural mismatch

The primary WebSocket path made the Python development lab responsible for raw GPT-Live PCM packet handling, provider/device sample-rate conversion, jitter buffering, PortAudio scheduling, interruption drain, and Windows audio backend behavior.

That is appropriate for server-owned audio streams but is unnecessary complexity for a user-facing PC/mobile client. GPT-Live WebRTC is designed to carry microphone and generated speech as negotiated media tracks while JSON events use the data channel.

## Repair2 decision

Add a loopback-only browser WebRTC lab:

- browser owns microphone and speaker media;
- Python keeps the OpenAI API key and brokers the SDP session creation;
- GPT-Live remains client-delegated;
- Live JSON events are normalized into the existing `VoiceFrontendEvent` contract;
- `LiveConversationBridge` and Conversation Core/Luna remain authoritative;
- the primary WebSocket implementation is retained for server/debug/fallback use.

## V1 comparison

V1's master architecture already recommended an Electron/React WebRTC interaction layer with a separate Python Core service, specifically identifying WebRTC as the robust client audio transport. Repair2 adopts that lesson while preserving v2 provider and authority boundaries.

## Deferred

This repair does not add remote authenticated clients, device pairing, TLS relay, production sideband controls, desktop Electron packaging, or autonomous background workers.
