# ISSUE 053 — 0.1.1 Local Wake/Sleep Lifecycle

## Problem

The 0.1.0 Desktop Alpha opened its Realtime voice session as soon as the app launched. That makes Jarvis behave like an always-open voice chat rather than a persistent assistant, leaves no true dormant presence, and makes future privacy/cost lifecycle policy harder to reason about.

## 0.1.1 decision

- Start desktop presence asleep.
- Keep sleeping microphone audio local to the user device/loopback Core.
- Use local Silero speech presence + local whisper.cpp final transcription + the provider-neutral wake phrase detector.
- Preserve the command after an embedded wake phrase and inject it into the newly opened Realtime conversation.
- Keep awake conversation continuous until explicit sleep or the 60-second inactivity timeout.
- Close Realtime before returning to local sleep.
- Treat typed input while sleeping as an intentional manual wake path.
- Keep presence separate from activity state.

## Production caveat

Full local Whisper transcription is heavier than a dedicated wake-word engine. It is acceptable for the alpha because it reuses an existing local provider and preserves full-command wake behavior, but low-end/mobile production should benchmark a dedicated keyword spotter. `LocalWakeListener` owns no microphone or transport so that replacement does not require rewriting Conversation Core or the app lifecycle.

## Desktop alpha background note

Electron disables renderer background throttling so local wake audio processing remains armed while the window is minimized. This is correct for assistant behavior but is not the final low-power design: a production native/audio worker or AudioWorklet-style wake capture should be benchmarked so minimized wake reliability does not require keeping unrelated renderer animation work active.
