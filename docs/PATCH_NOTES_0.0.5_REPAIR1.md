# 0.0.5 Repair1 — Barge-In Arming + Resident Qwen Cancellation

The first 0.0.5 live wake test successfully detected a full-sentence wake command,
then failed with `RuntimeError: streaming sidecar exited unexpectedly (1)` before
Jarvis could answer.

## Root cause

The first candidate reopened the microphone immediately after the wake transcript
was committed, before Luna/Qwen had produced audible output. Any residual/noise
`voice.speech.started` event could therefore be interpreted as a barge-in while
Qwen was starting synthesis.

Normal Qwen cancellation also hard-killed the resident sidecar. A synthesis
coroutine already blocked on sidecar stdout then observed EOF and surfaced that
expected cancellation as an unexpected worker crash.

## Repair

- Full-duplex capture is armed only when the current response is about to send its
  first PCM frame to playback. Barge-in therefore means "user speech while Jarvis
  is actually speaking", not residual audio while Luna is thinking.
- Playback is aborted before provider cancellation so audible stop remains fast.
- Qwen cancellation is cooperative and resident. The provider writes a per-request
  cancel flag; the sidecar checks it between streaming chunks, closes the active
  generator, emits a terminal `cancelled` event, and keeps the loaded model,
  compiled kernels, and prepared voice alive for the next response.
- The provider keeps draining framed PCM after local cancellation until the
  `cancelled` terminal event, preventing protocol desynchronization.
- A 5-second cancellation fail-safe still hard-restarts Qwen if a cooperative
  cancellation becomes stuck.

No wake/sleep policy, Luna model, Whisper mode, whole-response voice policy, or
60-second inactivity behavior changes in this repair.
