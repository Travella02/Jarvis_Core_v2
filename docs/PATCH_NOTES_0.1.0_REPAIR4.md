# 0.1.0 Repair4 — Playback State + Responsive Presence

Repair4 is a desktop-presentation repair on top of accepted Repair3.

## Changes

- Keeps `SPEAKING` active until WebRTC reports `output_audio_buffer.stopped` rather than allowing transcript completion to end the state early.
- Handles `output_audio_buffer.cleared` for barge-in/cancellation without clobbering a newer listening/thinking state.
- Leaves character-by-character captions presentation-only; captions no longer own product state.
- Flushes any tiny remaining caption backlog at actual playback completion so the final visible sentence is complete with the final audible word.
- Makes the Jarvis presence responsive using `vmin`-based proportions for the orb, transcript, composer, labels, and spacing.
- Uses `ResizeObserver` to keep the canvas backing resolution matched to the responsive rendered orb size.

## Deliberately unchanged

- `gpt-realtime-2.1-mini` remains the default conversational frontend.
- Cedar remains the test/default voice.
- Browser/Electron WebRTC remains the preferred media transport.
- Semantic VAD, Core delegation, memory/tool authority, latency telemetry, and Repair3 state blending are unchanged.

## Reference lesson

V1 distinguished provider response completion from actual WebRTC audio lifecycle. Repair4 preserves that lesson without bringing V1 runtime coupling into v2.
