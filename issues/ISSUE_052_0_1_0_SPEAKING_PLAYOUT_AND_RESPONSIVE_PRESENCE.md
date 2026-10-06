# ISSUE 052 — Desktop speaking state ended before audible playback / fixed-size presence

## Symptom

In the 0.1.0 Repair3 desktop alpha, the orb could leave `SPEAKING` before Cedar had audibly finished the last buffered words. The presentation also stayed near its original fixed pixel size when the Electron window was enlarged or fullscreened.

## Cause

Two presentation concerns were still tied to generation-time assumptions:

1. Caption pacing could reach the end of generated transcript before WebRTC playout had drained, allowing the UI to settle toward `READY` while audio was still audible.
2. The particle canvas and surrounding composition used fixed pixel dimensions inherited from the first alpha layout rather than viewport-relative presence sizing.

## V1 lesson reused

The V1 desktop reference already treated `output_audio_buffer.started` and `output_audio_buffer.stopped` as media lifecycle boundaries instead of assuming `response.done` meant the user had finished hearing the answer. Repair4 carries that boundary forward while keeping v2's presentation-only desktop client.

## Repair4 resolution

- `output_audio_buffer.started` owns entry into `SPEAKING`.
- `output_audio_buffer.stopped` owns normal exit from audible speaking.
- `output_audio_buffer.cleared` handles interruption/cancellation without overwriting a newer `LISTENING` or `THINKING` state.
- Caption pacing no longer changes the Jarvis product state.
- The particle canvas observes its rendered size and increases its backing resolution as the viewport changes.
- The orb, caption, composer, labels, and spacing use the smaller viewport dimension (`vmin`) so Jarvis maintains approximately the same visual proportion across window sizes and monitor resolutions.

## Authority boundary

No voice-model, turn-detection, Core, permission, memory, tool, or delegation behavior changes in this repair.
