# ISSUE-014 — TTS Prosody & Warm Session Latency

## Status
Addressed in 0.0.4-repair9 candidate; live acceptance pending.

## Live evidence
Repair8 on the RTX 5080 laptop measured:

- endpoint -> STT final: 78 ms
- STT final -> Luna first text: 2,984 ms
- Luna first text -> first speech chunk: 110 ms
- TTS request -> first waveform: 1,812 ms
- first waveform -> first audible audio: 63 ms
- speech end -> first audible audio: 5,047 ms

The spoken output also paused unnaturally inside sentences.

## Root cause
Repair8 optimized first-audio latency by allowing a character-limit cut before a natural sentence boundary. Chatterbox Turbo normalizes each independent synthesis request as an utterance and adds terminal silence, so a mid-clause chunk becomes an artificial sentence boundary with reset prosody.

The Voice Lab also exited after one turn, which meant every Luna latency sample included a fresh process/client connection instead of representing an ongoing Jarvis session.

## Repair9 policy
- Never cut ordinary spoken output mid-clause just to satisfy the soft latency target.
- Ask Luna to lead with a short complete first sentence.
- Keep an emergency hard cap for pathological unpunctuated output.
- Use low output verbosity for voice turns while keeping Luna reasoning at `none`.
- Run Chatterbox synthesis under `torch.inference_mode()`.
- Support multi-turn Voice Lab sessions so Whisper, Chatterbox, Conversation Core, and the OpenAI client remain warm between turns.

## Acceptance goal
Evaluate at least three turns in one process. Compare turn 1 with turns 2–3 before deciding whether Luna HTTP/Responses transport or Chatterbox Turbo itself must be replaced/optimized further.
