# 0.0.5 — Realtime Conversation Control

0.0.5 starts from the accepted/committed 0.0.4 voice pipeline and changes one vertical slice only: wake, sleep, continuous awake conversation, and interruption.

## User-visible behavior

- Jarvis starts sleeping by default.
- While sleeping, speech is transcribed locally but ignored unless it begins with a configured wake phrase.
- Full-sentence wake commands work in one utterance. `Hey Jarvis, what are the latest updates in Rocket League?` wakes Jarvis and submits `what are the latest updates in Rocket League?` immediately.
- Once awake, follow-up conversation stays awake without repeating the wake phrase.
- Explicit sleep phrases return Jarvis to sleep without another model reply.
- After 60 seconds of true awake inactivity (no accepted user speech and Jarvis not speaking), Jarvis sleeps automatically.
- While Jarvis is responding, the microphone is active. Endpoint-confirmed new user speech requests immediate playback stop and becomes the next utterance.

## Interruption continuity

0.0.4 recorded generated text as if it were heard. 0.0.5 separates those concepts.

On interrupted playback Core records:
- full generated assistant text (still in transcript/history);
- exact provider/source PCM bytes written;
- source-audio playback duration written;
- approximate text prefix the user heard;
- alignment method (`pcm-fraction` when complete synthesis is known, otherwise a conservative speech-rate estimate).

The next voice request carries this as a private developer playback-context input. GPT-6 Luna is told not to assume the unheard remainder was heard. The normal Responses WebSocket `previous_response_id` chain is retained when the local transcript chain still matches.

## Configurable wake/sleep

Defaults:
- wake: `hey jarvis`, `jarvis`
- sleep includes: `that's all`, `that's all jarvis`, `go to sleep`, `go to sleep jarvis`, `goodnight jarvis`
- idle sleep: 60 seconds

Environment configuration:
- `JARVIS_WAKE_PHRASES` (pipe-separated)
- `JARVIS_SLEEP_PHRASES` (pipe-separated)
- `JARVIS_IDLE_SLEEP_SECONDS`

Voice Lab overrides:
- repeat `--wake-phrase`
- repeat `--sleep-phrase`
- `--idle-sleep-seconds`
- `--start-awake` for development only
- `--legacy-half-duplex` for regression comparison only

## Architecture boundary

`VoicePresenceState` contains only `sleeping` and `awake`. Future product/activity states such as working, researching, thinking, waiting, or error are intentionally not implemented in 0.0.5 and can be layered independently later.

## Known limitations

- The new duplex path is headset-first. Production acoustic echo cancellation/noise suppression is not included; loudspeaker echo can falsely resemble barge-in speech.
- Qwen does not currently expose word timestamps through this adapter, so heard-text alignment is explicitly approximate. Exact PCM playback timing is retained for a future aligner.
- This milestone does not add tools, memory, UI, autonomous work, working/researching modes, or emotional/prosodic personality work.
