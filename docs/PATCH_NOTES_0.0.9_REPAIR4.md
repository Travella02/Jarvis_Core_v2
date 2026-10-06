# Jarvis Core v2 0.0.9 Repair4 - OpenAI Realtime WebRTC A/B

Repair4 adds an OpenAI Realtime 2.1 browser-WebRTC frontend beside GPT-Live and the local Whisper/Luna/Qwen chain. It does not choose a winner yet.

## Added
- `providers/voice_frontend/openai_realtime/` configuration, WebRTC call creation, trusted localhost relay, and Core delegation adapter.
- `apps.gpt_realtime_webrtc_lab` and a browser WebRTC test page.
- `delegate_to_jarvis_core` as the only Realtime application function in this A/B candidate.
- Realtime model/voice/reasoning selection (`gpt-realtime-2.1`, `gpt-realtime-2.1-mini`, voices such as Cedar/Marin).
- Realtime usage token telemetry from `response.done`.
- Best-effort server-side Realtime call hangup during lab teardown.
- Provider-neutral SDP normalization shared by GPT-Live and Realtime.

## Authority rules
- Simple/general conversation may stay inside Realtime.
- Durable memory, private/project state, actions, permissions, background work, and stronger reasoning delegate to Jarvis Core.
- Core remains authoritative and may route delegated work to Luna today or a stronger/future IntelligenceProvider later.
- Realtime never gets unrestricted shell, desktop, memory DB, or permission authority.

## Conversation while backend works
Realtime function calls do not block the WebRTC session. A natural acknowledgement can be spoken when real work begins, while Core runs asynchronously. When the function result arrives, Core sends `function_call_output` and triggers the continuation response. User interruption/follow-up remains available while Core is working.

## Lifecycle
The browser now closes its WebRTC peer when the localhost Jarvis Core control channel closes. The Realtime lab also requests the provider-side hangup endpoint during teardown.

## Not changed
Memory implementation, tool gateway, permission system, Runtime API, Luna provider, GPT-Live provider behavior, local Whisper/Qwen path, and durable autonomous task execution are unchanged.
