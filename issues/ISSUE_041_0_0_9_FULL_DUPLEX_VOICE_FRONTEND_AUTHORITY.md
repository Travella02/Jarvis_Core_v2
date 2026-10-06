# ISSUE-041 — Full-duplex voice must not become a second Jarvis authority

## Symptom / risk

The accepted local voice chain (Whisper -> Conversation Core/Luna -> Qwen) keeps reasoning and durable state inside Jarvis Core, but its sequential STT/LLM/TTS path can feel less natural and can expose local TTS artifacts. A native full-duplex voice service can improve turn-taking and interruption, but directly embedding reasoning, memory, tools, permissions, or task state inside that service would recreate the coupling problems already seen in V1.

## V1 reference review before implementation

The read-only V1 0.3.6 reference was reviewed before 0.0.9.

Relevant lessons:

- **ISSUE-241 — Voice engine was tightly coupled to Jarvis reasoning.** Changing the voice transport must not require changing reasoning, memory, actions, or personality ownership.
- **ISSUE-160 — Realtime model was planning external actions.** Expensive/realtime speech generation must not become the action planner or tool authority.
- **ISSUE-221 — Realtime response could replace grounded Connected Action confirmation.** A conversational speech layer must never contradict verified action state or present an ungrounded success/failure result.

## 0.0.9 design

- Add a provider-neutral `VoiceFrontendProvider` / `VoiceFrontendSession` contract above concrete STT/TTS providers.
- Keep the accepted local Whisper/Luna/Qwen path intact as the rollback and economy baseline.
- Add OpenAI GPT-Live only under `providers/voice_frontend/openai_live/`.
- Use **client delegation**, so meaningful requests return to the existing `ConversationCore.submit_voice()` path and configured intelligence provider.
- Keep memory, tools, permissions, tasks, runtime state, and durable application data in Jarvis Core.
- Return verified backend results to GPT-Live using commentary; GPT-Live may phrase them naturally but must not invent backend facts or action outcomes.
- Newer live delegations invalidate stale backend commentary. Conversation Core remains cancellation authority.

## Acceptance

0.0.9 is accepted only if:

1. the provider-neutral contract and bridge tests pass;
2. the existing full regression remains green;
3. the local voice path still passes its regression test;
4. a live GPT-Live A/B session can carry five substantive turns through client delegation into the existing Conversation Core/Luna path;
5. one natural interruption/correction does not allow stale backend commentary to overwrite the newer request;
6. GPT-Live can be removed/replaced without moving memory or intelligence authority out of Core.

## Deferred production concerns

The 0.0.9 A/B lab does not yet claim production wake/sleep lifecycle, exact physical-playback reconciliation for GPT-Live paraphrases, durable session transcript reconciliation, autonomous cloud workers, tool/permission execution through the Live path, remote/mobile WebRTC transport, or custom voices. Those require separate acceptance boundaries.
