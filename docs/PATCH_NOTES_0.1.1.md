# 0.1.1 — Wake/Sleep Presence Control

## Scope

0.1.1 adds the first real desktop presence lifecycle without changing the chosen Realtime Mini + Cedar + WebRTC conversational architecture.

### Added

- local-only sleeping wake lane using loopback PCM, Silero VAD, whisper.cpp, and the existing configurable `WakePhraseDetector`,
- same-utterance wake preservation (`Jarvis, <request>` -> wake + `<request>`),
- explicit Realtime lifecycle sleep signal that never delegates to Luna/Core reasoning,
- 60-second inactivity auto-sleep,
- typed manual wake into the same Realtime conversation,
- sleeping/waking orb states using the existing smoothly blended particle system,
- desktop health/config presence fields and wake/sleep endpoints,
- local wake provider contract tests and desktop lifecycle regression coverage.

### Preserved

- Jarvis Core authority,
- Realtime 2.1 Mini + Cedar + WebRTC as current default conversational frontend,
- Core delegation for memory/tools/tasks/deeper reasoning,
- actual WebRTC playback owning `SPEAKING`,
- responsive particle presence and character-paced captions,
- swappable conversational/backend provider boundaries.

### Deliberately deferred

- user-editable wake word UI,
- dedicated low-power keyword-spotting provider,
- mobile/background OS wake integration,
- cloud/remote wake,
- acoustic echo cancellation improvements beyond the browser media stack,
- durable cross-session chat history.
