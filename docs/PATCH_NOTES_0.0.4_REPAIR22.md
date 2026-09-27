# 0.0.4 Repair22 — Qwen True-Streaming Candidate

Repair22 is an isolated experiment, not a provider replacement. Repair20 remains the accepted live baseline.

The official Qwen API used by Repair20 returns a complete waveform from `generate_voice_clone`; its `non_streaming_mode=False` option does not provide true streaming generation. This candidate uses the experimental dffdeeq/Qwen3-TTS-streaming fork, which exposes `stream_generate_voice_clone()` and emits PCM incrementally.

Repair22 adds only a setup script, a candidate benchmark app/worker, tests, and this documentation. It does not modify the accepted Qwen provider, Voice Lab, Conversation Core, Whisper, Luna, `.env`, or the main `.venv`.

Acceptance is evidence-based: first audio should arrive materially before full generation completes; playback should remain continuous; voice quality must remain acceptable; and real-time factor should be near or below 1.0 for sustained speech. If it fails those gates, remove/reject the candidate and retain Repair20.
