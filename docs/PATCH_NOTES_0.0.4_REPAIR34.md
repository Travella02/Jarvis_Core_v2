# Jarvis Core v2 0.0.4 Repair34 — Endpointed Whisper Final-Only A/B

Repair33 is the committed whole-response TTS baseline. It substantially improved
naturalness at about 1.1-1.3 seconds first-audible latency.

## Observation

Voice Core currently:
1. captures the microphone;
2. performs VAD/endpointing;
3. evidence-gates the complete candidate;
4. only then hands the accepted, already-complete utterance to whisper.cpp.

The whisper.cpp adapter still schedules a rolling partial inference over those
buffered frames and then performs another full final inference. Because endpointing
is already complete, that partial cannot make Conversation Core start sooner.

## Candidate

`--stt-endpoint-final-only`

In this mode:
- the exact same evidence-approved audio frames are retained;
- Whisper runs one full final transcription;
- the redundant post-endpoint partial inference is skipped;
- transcript/model/audio quality settings do not change.

The default remains the committed behavior unless the A/B flag is supplied.

## Humanization

Repair34 touches only the local STT scheduling path. It does not alter Luna,
Jarvis personality, response length, humor, memory, whole-response Qwen, fixed
seed, or playback.

## Expected result

`endpoint -> STT final` should fall if the duplicate inference is a meaningful
portion of the current ~170-220 ms. Any gain directly reduces first-audible
latency without making Jarvis speak less.
