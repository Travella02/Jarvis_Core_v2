# Jarvis Core v2 0.1.0 Repair1 — Desktop Presence Polish

## Scope

Repair1 is deliberately limited to the first Desktop Alpha user experience. It does not change the accepted Realtime 2.1 Mini, Cedar, WebRTC, Core delegation, memory, permissions, tools, or backend model-routing architecture.

## Changes

- Replaced the original ring/orbit placeholder with a code-native flowing particle orb rendered on an HTML canvas. The orb remains presentation-only and reacts to listening, thinking, speaking, working, connecting, and error states.
- Added paced caption rendering. Realtime output-audio transcript deltas are queued and released at a speech-like cadence instead of being dumped to the screen as fast as the model can generate text.
- Cancelled/interrupted responses discard caption backlog that may have been generated but never spoken.
- Added renderer-to-Core latency telemetry for speech stop, response creation, first transcript, and first WebRTC output-audio-buffer start. The host prints compact per-turn timing lines so perceived latency can be diagnosed before changing VAD behavior.
- Replaced the root `StaticFiles` mount with GET-only file/fallback routes. WebSocket scopes can no longer fall through into Starlette StaticFiles and trigger the HTTP-only assertion seen in live Desktop Alpha testing.

## Explicit non-changes

- No Realtime model change.
- No Cedar voice change.
- No VAD/eagerness change.
- No WebRTC media-path change.
- No Core delegation or authority change.
- No added OpenAI call for captions; the UI renders transcript events from the existing Realtime response.
