# Testing 0.0.4-repair13

1. Run `python -m unittest discover -s tests -v` and expect 142 passing tests.
2. Run `python -m apps.voice_benchmark` and expect 6/6.
3. Confirm microphone device 1 is still live with:
   `python -m apps.voice_lab --mic-test --input-device 1 --mic-test-seconds 5`
4. Run Qwen with the saved profile:
   `python -m apps.voice_lab --turns 3 --tts-provider qwen3 --voice-profile tanner-test --input-device 1`
5. Speak normally. A VAD miss may print `Acoustic speech rescue engaged ...`; Jarvis should still endpoint, transcribe, and answer.
6. Remain quiet for several seconds once. Low-energy noise must not become a user turn.

Do not clean or commit until live acceptance passes.
