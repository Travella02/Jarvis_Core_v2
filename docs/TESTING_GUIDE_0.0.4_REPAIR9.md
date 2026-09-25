# 0.0.4-repair9 Live Testing Guide

1. Run automated tests:

   `python -m unittest discover -s tests -v`

2. Run deterministic Voice benchmark:

   `python -m apps.voice_benchmark`

3. Confirm providers:

   `python -m apps.voice_lab --provider-health`

4. Run a three-turn warm Voice Lab session:

   `python -m apps.voice_lab --turns 3`

Use short conversational prompts on all three turns. For the first turn, repeat the prior space test if useful. On turns two and three, ask follow-ups so Conversation Core context is also exercised.

Evaluate:

- no pause inside an ordinary sentence caused by TTS chunk boundaries;
- pronunciation/prosody continuity across the first sentence;
- turn 2/3 `STT final -> Luna first text` compared with turn 1;
- `TTS request -> first waveform` after the Chatterbox worker is already warm;
- speech-end -> first-audible latency.

Do not commit 0.0.4 until live acceptance is complete.
