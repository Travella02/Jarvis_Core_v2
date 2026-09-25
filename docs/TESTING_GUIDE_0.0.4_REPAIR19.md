# 0.0.4-repair19 Live Acceptance

1. Install the updated dependencies because the OpenAI SDK WebSocket extra is now required:

   `python -m pip install -r requirements.txt`

2. Run:

   `python -m unittest discover -s tests -v`

   Expected: 161 tests, OK.

3. Run:

   `python -m apps.voice_benchmark`

   Expected: 6/6 passed.

4. Confirm Qwen/Whisper health as before.

5. Run five warm voice turns with Qwen:

   `python -m apps.voice_lab --turns 5 --tts-provider qwen3 --voice-profile tanner-test --input-device 1`

   Voice Lab defaults to `--luna-transport websocket` in this repair.

6. Compare with HTTP using the same process/prompt set:

   `python -m apps.voice_lab --turns 5 --tts-provider qwen3 --voice-profile tanner-test --input-device 1 --luna-transport http`

Record turns 2–5 for:

- endpoint -> STT final
- STT final -> Luna first text
- Luna first text -> first speech chunk
- TTS request -> first waveform
- speech end -> first audible audio
- first spoken chunk word/character count

Acceptance goal for this repair is evidence of lower/more consistent warm latency without degraded transcript accuracy or unnatural first-clause prosody. If WebSocket gives no meaningful advantage, retain HTTP and do not force the transport into production.
