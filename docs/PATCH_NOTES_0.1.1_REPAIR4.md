# 0.1.1 Repair4 — Audio-Safe Response Budget

- Raises ordinary Realtime `max_output_tokens` from 80 to 320.
- Raises explicit expanded-response budget from 320 to 1024.
- Keeps the conversational target at roughly 20–45 spoken words for ordinary answers.
- Treats the token limit as a runaway guard, not a word-count target.
- Adds per-response output/text/audio token telemetry to the desktop host.
- Does not change Realtime Mini, Cedar, WebRTC, wake/sleep, Core delegation, or the Jarvis persona.
