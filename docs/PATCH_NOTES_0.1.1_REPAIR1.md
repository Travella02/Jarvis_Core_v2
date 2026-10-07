# Jarvis Core v2 0.1.1 Repair1 — Silent Sleep + Conversational Brevity

This repair addresses three live-acceptance findings without changing the 0.1.1 wake architecture:

- explicit sleep becomes silent immediately: Realtime is instructed to use `sleep_jarvis` as the only response, while the client cancels the active response, clears output/input buffers, pauses/mutes local WebRTC playback, and then tears down the session;
- entering sleep clears the visible response caption so sleeping presence returns to only Jarvis's dormant visual state and wake affordance;
- ordinary Realtime Mini answers now default to one to three natural sentences, with explicit protection for personality, humor, warmth, and detail when requested or actually needed.

Realtime Mini, Cedar, WebRTC, local wake detection, Core delegation, idle sleep, and provider swappability are otherwise unchanged.
