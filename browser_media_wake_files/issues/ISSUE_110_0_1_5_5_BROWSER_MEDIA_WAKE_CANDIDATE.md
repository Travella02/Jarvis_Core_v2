# Issue 110 — Generalized browser interaction and wake mis-transcription

Observations motivating this candidate:
- `Close Google` was understood as browser intent but denied by 0.1.5.4 because only `close_tab` for current tab existed.
- Wake STT frequently transcribes `Jarvis` as `Jervis` or `Dervis` and fails to wake Jarvis, even when clearly addressed.
- Media controls do not exist yet.

Candidate approach:
- Keep existing Core ownership and fast Mini parallel voice path.
- Offer new opt-in mode instead of mutating accepted `managed-browser` behavior.
- Validate tab targets against independent transcript and current browser page hosts; refuse duplicate matches.
- Fixed static HTML5 media operations only; authorize explicit absolute volume from user transcript; never act on arbitrary model-supplied scripts or targets.
- Apply narrow, opt-in transcription-tolerant wake name match, leaving VAD/barge-in unaffected.

Acceptance pending Windows live tests. Follow-up issues: video selection, iframe sites, seek/fullscreen, multi-step verified actions, broader/safer wake matching.
