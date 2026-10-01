# ISSUE-029 — Ghost transcripts need independent speech-presence authority

## Symptom

Repair4 substantially improved realtime interruption but silence could still be
transcribed as plausible phrases such as `Thank you.`. Those phrases became real
user turns, causing Jarvis to respond repeatedly despite nobody speaking.

The same live run also ended with pending STT/audio tasks and
`RuntimeError: cannot reuse already awaited coroutine` during shutdown.

## Root cause

Repair4 made one Whisper stream the transcript authority, but still allowed the
transcript itself to help prove that a speech candidate was real. That is circular:
a recognizer capable of hallucinating on silence cannot be the only independent
proof that speech existed.

V1 avoided this class of failure because its realtime/provider speech-start event
owned physical speech presence and transcript events described content afterward.

## Repair5

- Add Silero VAD v6.2.0 through whisper.cpp's native streaming VAD-only API.
- Continuous 0.0.5 uses Silero as the sole speech-presence authority.
- Start Whisper only after neural speech onset is established.
- Never use RMS/peak to authorize a turn.
- Barge in immediately on trusted neural speech-start; continue the same capture
  through Whisper for the final next-turn text.
- Reset neural VAD state between utterances.
- Cooperatively cancel listeners before hard task cancellation to allow nested
  audio/STT generators to unwind cleanly.

## Deferred

Acoustic echo cancellation and speaker attribution remain separate future work.
Speech from another human/device can still be legitimate acoustic speech even if it
is not the intended speaker; Repair5 solves silence hallucination authority, not
speaker identity.
