# Patch Notes — 0.0.1 - Foundation

## Purpose

Create the first testable Jarvis Core v2 foundation without introducing provider SDKs, realtime audio implementation, or legacy V1 architecture.

## Added

- Canonical repository structure for apps/core/providers/integrations/backend/prompts/tests/issues/scripts/docs.
- `VERSION` = `0.0.1` and minimal Python/Node project metadata.
- Provider-neutral `IntelligenceProvider` contract and stream event/context/health metadata types.
- Typed non-executable tool definitions/requests/results that keep execution authority outside model providers.
- ORVEX-owned audio/STT/TTS/VoiceProfile contracts without implementing the realtime engine.
- Cross-boundary cancellation and correlation primitives.
- Local-only diagnostic command: `python -m core.diagnostics`.
- V1 fallback inventory and core architecture decisions.
- Issue/update documentation discipline and 0.0.1 foundation issue record.
- Unit/contract tests that guard provider independence, non-executable tool metadata, project structure, and side-effect-free diagnostics.

## Explicitly not included

- OpenAI SDK or GPT-5.6 Luna connection (0.0.2).
- Conversation state machine/referent resolver (0.0.3).
- Audio capture/VAD/STT/TTS runtime (0.0.4+).
- Permission engine or tool execution (later milestone).
- V1 source copied into v2 runtime.
