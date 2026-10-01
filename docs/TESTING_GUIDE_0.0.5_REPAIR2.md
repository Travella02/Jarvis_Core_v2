# Testing Guide — 0.0.5 Repair2

Focused regression:

`python -m unittest tests.unit.test_0_0_5_barge_in_arm tests.unit.test_0_0_5_qwen_resident_cancel tests.integration.test_0_0_5_continuous_session tests.integration.test_0_0_5_interruption_context -v`

Expected: 11 tests, OK.

Full regression:

`python -m unittest discover -s tests -v`

Expected on the verified Repair2 tree: 244 tests, OK.

## Live test

Use the same Voice Lab command as the initial 0.0.5 candidate.

Verify these cases separately:

1. Sleeping speech without wake phrase is ignored.
2. “Hey Jarvis, tell me something interesting about space.” wakes and processes the command in the same utterance.
3. While Jarvis is still thinking (before audio starts), say a clear follow-up such as “Actually, explain neutron stars instead.” Jarvis should cancel the active turn and use the new utterance.
4. While Jarvis is audibly speaking, interrupt him. Audio should stop quickly and the same utterance should become the next turn.
5. Tiny noise/raw onset should not cancel an active response unless speech becomes sustained enough to emit `voice.speech.confirmed`.
6. The next model turn should receive interruption context including the phase and, for spoken interruptions, approximate heard text/playback position.
7. Qwen should stay resident across normal interruption; there should be no new cold model load.
8. Explicit sleep and 60-second inactivity sleep should remain unchanged.
