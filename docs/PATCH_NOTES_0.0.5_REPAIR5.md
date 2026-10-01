# Jarvis Core v2 0.0.5 Repair5 — Independent Neural Speech Presence

## Why Repair4 was still wrong

Repair4 improved capture substantially, but it still allowed Whisper to participate
in proving that speech existed. That creates a circular authority problem: Whisper
is the component that can hallucinate a plausible phrase such as `Thank you.` on
silence, so a plausible Whisper transcript cannot also be sufficient evidence that
a human physically spoke.

The live Repair4 run demonstrated exactly that failure: the voice path worked, but
silence repeatedly became `You: Thank you.` and Jarvis replied to a person who had
not spoken.

## V1 comparison

The stable V1 interruption design had a stronger separation of responsibility:

1. the realtime/provider speech-start signal established that the user actually
   began speaking;
2. transcript events described what that already-established speech said;
3. barge-in could happen immediately on the trusted speech-start signal;
4. the same user utterance then continued through transcription as the next turn.

Repair5 recreates that ownership model locally rather than copying V1's cloud
voice stack.

## Repair5 architecture

Continuous 0.0.5 Voice Lab now uses Silero VAD v6.2.0 through whisper.cpp's public
VAD-only C API as the independent speech-presence authority:

`microphone -> Silero neural VAD -> speech-start -> Whisper -> text`

Important consequences:

- Whisper is not started until neural VAD confirms speech onset.
- A Whisper silence hallucination can no longer create a user turn because there
  is no STT request for audio that never passed neural speech presence.
- PCM RMS/peak remain diagnostics only. Loud audio cannot bypass neural VAD and
  quiet speech is not rejected by a hard amplitude threshold.
- During an active Jarvis response, trusted `voice.speech.started` immediately
  triggers barge-in, matching the V1 interruption timing model. Whisper continues
  recording the same utterance to provide the final next-turn text.
- The detector state resets between utterances as required by whisper.cpp's
  streaming VAD API.

Legacy `--legacy-half-duplex` keeps the old WebRTC VAD path solely as an A/B / rollback
path. Realtime 0.0.5 continuous control defaults to Silero.

## Runtime footprint

No Torch, ONNX Runtime, or new cloud service is added. Repair5 reuses the already
built whisper.cpp DLL and adds only the official `ggml-silero-v6.2.0.bin` model
(~885 KB), downloaded by `scripts/setup_whisper_vad.ps1` with a pinned SHA-256.

## Shutdown repair

Repair4's live session also exposed pending task / `cannot reuse already awaited
coroutine` messages during shutdown. Listener cancellation now requests cooperative
capture cancellation first and waits for the audio/STT stack to unwind before using
`Task.cancel()` as a bounded fallback.

## Scope

This repair changes speech ownership / interruption plumbing only. Wake phrases,
60-second sleep policy, GPT-6 Luna continuation, whole-response Qwen voice behavior,
and future activity modes remain otherwise unchanged.
