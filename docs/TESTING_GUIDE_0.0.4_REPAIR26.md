# Testing Guide — 0.0.4 Repair26

Run:
`python -m unittest tests.unit.test_audio_playback_result tests.unit.test_sounddevice_output_latency_policy tests.unit.test_repair26_playback_telemetry -v`

Then:
`python -m unittest discover -s tests -v`

Then the same five-turn Voice Lab:
`python -m apps.voice_lab --turns 5 --tts-provider qwen3-streaming --voice-profile tanner-test --input-device 1`

Watch:
- startup buffer ready -> first PCM write
- first PCM write -> estimated audible audio
- first PCM write blocking duration
- speech end -> first audible audio

The old ~400 ms should mostly appear as blocking-write duration instead of
being misreported as startup latency. Audio must remain smooth.
