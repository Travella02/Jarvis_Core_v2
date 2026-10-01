# ISSUE 026 — 0.0.5 Full-Duplex AEC and Exact Word Alignment Are Deferred

## Status
Known limitation / deferred.

## Context
0.0.5 deliberately establishes wake/sleep and interruption semantics before adding a production acoustic echo canceller. The development headset path can run microphone capture while TTS is playing, but loudspeaker playback may re-enter the microphone and look like barge-in speech.

Qwen streaming also does not currently expose word-level timestamps through the accepted adapter. 0.0.5 therefore preserves exact source PCM playback duration/bytes and an explicitly approximate heard-text prefix.

## Required future work
- provider-neutral AEC/noise suppression integration;
- echo/barge-in regression corpus across headset, laptop speakers, and external speakers;
- optional forced alignment or TTS-native timestamps for word-accurate heard/unheard boundaries;
- keep all of this below Conversation Core so STT/TTS providers remain replaceable.
