# 0.0.4-repair8 — Realtime Response Pipeline

This repair addresses the first successful end-to-end Voice Lab latency measurement without changing the selected STT/TTS candidates.

## Changes

- Luna's default Jarvis reasoning policy is now `none` / fastest, with automatic reasoning escalation disabled for the current path.
- Typed/voice development labs default to the same fastest policy. Explicit higher levels remain development overrides for future policy work.
- Voice Conversation Core injects a concise spoken-response instruction while typed turns remain unchanged.
- `SpeechTextChunker` uses a tighter opening-phrase soft limit and larger later chunks.
- New provider-neutral speech normalization removes markdown/display artifacts before TTS while preserving the original response text in Conversation Core.
- Voice response flow now has independent model-delta, speech-chunk, synthesized-audio, and playback stages. Chatterbox remains one persistent sidecar; next chunks can synthesize while prior audio is physically playing.
- Audio output is fed one continuous response stream instead of reopening the physical output stream per phrase.
- Telemetry now records `speech_first_chunk_ready`, `tts_first_request_started`, and `tts_first_waveform_ready` in addition to the existing marks.

## Non-goals

- No Sol router is introduced here. Provider/model escalation remains a later routing milestone.
- No full-duplex microphone/speaker operation, AEC, or acoustic barge-in is added; those remain 0.0.5.
- No claim is made that Chatterbox meets the final latency target until the live repair8 timings are measured.
