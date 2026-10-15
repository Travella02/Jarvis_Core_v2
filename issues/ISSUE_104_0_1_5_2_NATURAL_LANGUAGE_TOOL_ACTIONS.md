# Issue 104 — Wire real approved-site action into Mini conversation

Status: live acceptance pending.

Problem: 0.1.5.1 Core gateway launched YouTube through a standalone demo but natural conversational requests were dry runs. Additional user request: silence beeping test cues.

Solution: explicitly opt-in A/B flag, same-turn transcript-bound Mini selection, independent Core gateway authorization, one-use turn guard, Core-result audio reuse, silent test-cue flag. Keep accepted voice system and previous guided variant unchanged.

Risks: model routing may incorrectly select direct; provider transcript errors; localhost control-channel origin and user identity are not yet production-hardened; excessive confirmed action retries should stay user-initiated. Re-test on real Windows microphone before accepting.
