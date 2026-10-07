# 0.1.1 Repair5 — Manual Response Policy / Natural Completion

- Stops using a tight Realtime token ceiling to force brevity; live testing proved that it clips Cedar mid-sentence.
- Raises ordinary response guardrail to 1024 tokens and explicit expanded responses to 2048 tokens.
- Keeps Semantic VAD for natural endpoint detection, but disables automatic response creation for the desktop session.
- The desktop renderer now manually sends `response.create` immediately on `speech_stopped`, using a response policy supplied by Jarvis Core.
- The normal per-turn policy requests at most two complete spoken sentences / about 35 words while preserving Jarvis personality.
- Explicit detail requests still use `request_expanded_response` before the long answer.
- Core delegation results receive a compact spoken-summary policy too.
- GPT-Realtime labs retain automatic response creation by default; this repair only changes the desktop orchestration path.
