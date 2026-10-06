# Jarvis Core v2 0.0.9 — Swappable Full-Duplex Voice Frontend / GPT-Live A/B Prototype

## Summary

0.0.9 adds a provider-neutral native-conversation voice frontend above Jarvis Core and implements OpenAI GPT-Live as the first full-duplex provider for A/B testing. The existing local Whisper -> Luna -> Qwen path is preserved unchanged as the accepted rollback/economy baseline.

The design intentionally does **not** turn GPT-Live into Jarvis's brain. GPT-Live handles realtime listening, speaking, natural turn-taking, and interruption within its voice session. Meaningful requests use GPT-Live client delegation and are routed back through the existing authoritative Conversation Core and configured intelligence provider (Luna by default). Memory, tools, permissions, task state, provider routing, and durable application state remain Core-owned.

## V1 reference review

Before implementation the read-only V1 0.3.6 checkpoint was reviewed, especially:

- `ISSUE_241_VOICE_ENGINE_WAS_TIGHTLY_COUPLED_TO_JARVIS_REASONING.md`;
- `ISSUE_160_REALTIME_MODEL_WAS_PLANNING_EXTERNAL_ACTIONS.md`;
- `ISSUE_221_REALTIME_RESPONSE_COULD_REPLACE_GROUNDED_CONNECTED_ACTION_CONFIRMATION.md`.

0.0.9 carries forward the separation lesson: voice presentation may be replaced without changing intelligence/memory ownership, and verified backend results remain authoritative.

## Added

### Provider-neutral full-duplex frontend contract

`core/voice/frontend.py` introduces:

- `VoiceFrontendProvider`;
- `VoiceFrontendSession`;
- `VoiceFrontendMetadata` / `VoiceFrontendHealth`;
- `VoiceFrontendSessionConfig`;
- provider-neutral frontend events for audio, transcripts, delegation, usage, lifecycle, and errors.

This contract is independent of GPT-Live and does not reference Luna, memory storage, tools, or permissions.

### Client-delegation bridge

`core/voice/live_bridge.py`:

- accumulates GPT-Live input transcript fragments using the provider timeline;
- maps `session.delegation.created` into the existing `ConversationCore.submit_voice()` path;
- sends completed Core results back through frontend commentary;
- keeps Core cancellation authority;
- uses a delegation revision so a newer correction cannot allow stale backend commentary to overwrite it;
- emits authoritative EventBus lifecycle events for received/completed/cancelled/failed/superseded delegations.

### OpenAI GPT-Live adapter

`providers/voice_frontend/openai_live/` implements the OpenAI-specific WebSocket transport behind the provider-neutral contract:

- `gpt-live-1` default model;
- `meridian` built-in voice for the A/B prototype;
- PCM16 mono at 24 kHz by default after 0.0.9 Repair1 (16 kHz remains an explicit supported override);
- client delegation only;
- transcript/audio/usage event conversion;
- graceful `session.close` handling;
- no new dependency (the accepted `websockets==15.0.1` remains sufficient).

The existing `OPENAI_API_KEY` is reused. No second credential is introduced.

### GPT-Live development A/B lab

`python -m apps.gpt_live_lab` creates the accepted `JarvisRuntime`, Conversation Core, and Luna provider, then connects GPT-Live as a replaceable voice frontend. It:

- streams the selected microphone to GPT-Live;
- plays returned Live PCM through the existing sounddevice integration;
- routes client delegations into Conversation Core/Luna;
- prints user/assistant transcript deltas;
- records backend delegation latency and observed Live usage seconds;
- prints the exact five manual acceptance phrases;
- supports `--doctor` without microphone/model/network use.

The lab is deliberately separate from the existing production-shaped wake/sleep Voice Lab so the A/B test cannot silently replace accepted behavior before live approval.

## Swappability / authority rules

- GPT-Live-specific code stays in its provider adapter.
- Conversation Core never imports GPT-Live.
- Memory stays in Core/application services, not in the Live provider.
- Intelligence routing remains behind `IntelligenceProvider`.
- The local Whisper/Qwen implementation remains available.
- Future native full-duplex providers can implement the same frontend contract.
- A newer delegation/correction suppresses stale prior commentary even if cancellation races with backend startup.

## Deferred

0.0.9 is an A/B prototype. It intentionally defers:

- replacing the accepted wake/sleep lifecycle with GPT-Live;
- exact physical-playback/"what was actually heard" reconciliation for Live-paraphrased speech;
- durable memory/session transcript reconciliation for non-delegated small talk;
- tool and permission execution through the Live path;
- long-running autonomous/cloud task workers;
- remote/mobile WebRTC transport and device authentication;
- custom voices;
- removing Whisper or Qwen.

## Repair2 transport update

Live acceptance now prefers the loopback browser WebRTC lab (`python -m apps.gpt_live_webrtc_lab --turns 5 --voice meridian`). The original primary-WebSocket PCM lab remains supported for server/debug/fallback use. WebRTC changes media transport only; client delegation still enters the same Jarvis Core/Luna bridge.


## Repair6 acceptance direction — Realtime 2.1 Mini + authoritative Core delegation

Live A/B testing selected OpenAI Realtime 2.1 Mini over WebRTC as the current default conversational frontend. It was materially more natural and responsive than the GPT-Live + backend-delegation path in the accepted user tests while remaining inexpensive enough for normal conversation. GPT-Live and the local Whisper/Qwen chain remain supported alternatives.

Repair6 finalizes the 0.0.9 foundation without moving authority into the conversational model:

- default Realtime model becomes `gpt-realtime-2.1-mini`; Cedar and low reasoning remain defaults;
- Realtime answers ordinary conversation directly and delegates only when Core-owned context/work or stronger backend help is needed;
- the delegation bridge remains model-neutral: Core chooses the current/future backend route;
- natural reactions/personality are preserved, while fake waiting language before immediate answers is explicitly discouraged;
- backend prewarm is opt-in in the lab so a voice session does not make a hidden Luna request unless requested;
- acceptance completion is tied to captured user turns plus the final non-tool response rather than raw `response.done` count, which could be inflated by function-call responses;
- the final response receives a larger playout grace before teardown to avoid clipping the last sentence;
- WebRTC remains the preferred client media transport, and the browser remains a test harness rather than a product requirement.

V1 review reinforced the same separation: realtime transport/conversation can be replaceable while Core/cloud authority, provider routing, and exact tool/memory truth remain outside the live model.
