# Jarvis Core v2 0.0.5 Repair2 — Phase-Independent Interruption

Repair1 moved duplex listening to playback start to avoid a Qwen cancellation race. That protected the resident TTS sidecar, but it narrowed interruption too far: users must be able to preempt Jarvis while he is thinking or preparing speech, not only after audio becomes playable.

Repair2 restores continuous listening throughout the active turn while replacing raw-onset cancellation with a stronger speech-confirmation contract.

## Changes

- The next microphone capture opens immediately after the current user turn is submitted.
- `voice.speech.started` remains fast telemetry/activity but does not cancel Jarvis.
- VoiceEngine emits `voice.speech.confirmed` only after 180 ms of sustained fused speech activity.
- Confirmed speech can cancel Jarvis during:
  - `thinking`
  - `synthesizing`
  - `speaking`
- The concurrently captured utterance continues through endpointing/STT and becomes the next turn.
- Cooperative Qwen cancellation from Repair1 remains unchanged; the resident model is not killed during normal interruption.
- Interruption context now records the phase in which the prior turn was interrupted. The next OpenAI turn is told whether interruption happened while thinking, synthesizing, or speaking, in addition to heard/unheard playback context.
- Continuous-session tests were rewritten to remove the playback-only assumption and to avoid timing-sensitive Windows races.

## Future compatibility

This creates one phase-independent user-preemption contract instead of a playback-only stop. Future working/researching/tool activity can attach their own cancellation handles to the same higher-level interruption path without changing wake/sleep semantics.

## Deliberately unchanged

- Wake phrase behavior
- Full-sentence wake + command
- 60-second idle sleep
- Explicit sleep phrases
- GPT-6 Luna model policy
- Whole-response Qwen voice path
- Final-only Whisper
- Qwen resident cooperative cancellation
