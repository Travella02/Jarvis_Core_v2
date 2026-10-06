# Jarvis Core v2 0.0.9 Repair5 — Realtime WebRTC Multipart Form Fix

## Problem
The first `gpt-realtime-2.1` browser WebRTC A/B attempt reached OpenAI but `/v1/realtime/calls` returned HTTP 400:

`Invalid multipart form, field "sdp" is required but not found`

Repair4 sent the SDP part with a filename (`offer.sdp`). That makes `httpx` serialize it as a file-upload part. OpenAI's Realtime unified WebRTC interface expects ordinary multipart form fields named `sdp` and `session`, matching `FormData.set("sdp", ...)` and `FormData.set("session", ...)`.

## Repair
- Send `sdp` as a filename-free multipart text field.
- Send `session` as a filename-free multipart text field.
- Preserve SDP normalization, trusted-server API-key handling, Realtime/Core delegation, WebRTC media, Cedar, and all existing provider abstractions unchanged.
- Add regression coverage that fails if either field becomes a file upload again.

## Scope
This is request framing only. It does not change Jarvis Core, Luna, GPT-Live, memory, tools, permissions, task routing, Realtime prompting, WebRTC browser media, or pricing behavior.
