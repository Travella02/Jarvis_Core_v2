# Jarvis Core v2 0.0.4 Repair26 — Low-Latency Output + Honest Playback Timing

Repair25 showed a suspiciously consistent ~391-407 ms between startup-buffer
release and `audio_first_played`. Inspection found that the first-write timestamp
was recorded only after blocking `RawOutputStream.write()` returned. With a
~320 ms Qwen PCM frame, most of that number was frame-drain time, not proof that
Jarvis had not started speaking.

Repair26:
- timestamps first PCM submission before the blocking write;
- records first-write completion separately;
- estimates first audible audio from PortAudio's reported output latency;
- requests PortAudio `latency="low"` and safely falls back to the default profile;
- keeps Repair25's 250 ms single-frame fast-start runway unchanged.

This is deliberately a measurement-first latency repair. It prevents us from
optimizing a fake ~400 ms bottleneck and may also reduce the real device buffer.
