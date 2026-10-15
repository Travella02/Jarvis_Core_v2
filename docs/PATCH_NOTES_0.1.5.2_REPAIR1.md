# Jarvis Core v2 — 0.1.5.2 Repair1: Natural Action UX & Quiet Tests

## Baseline
Requires 0.1.5.2 + Windows UTF-8 Testfix1 (not yet committed). Installer verifies original source checksums and refuses modified/unknown files.

## Scope
- Accept a narrowly-defined affirmative *user* request such as **"Jarvis, can you open YouTube for me?"** and **"Could you please open YouTube?"** in addition to **"Open YouTube"**. The model's proposal never authorizes execution; the same-turn user transcript and Core gateway remain authoritative.
- Keep negation, conditional, quoted, compound, unknown-site, duplicate, stale-turn, and missing-evidence requests non-executable. Only `youtube.com` remains allowlisted.
- On a successful visible browser action: leave Jarvis silent, clear the completion caption and return to Ready. On refusal/failure: show an accurate caption and return to Ready instead of being stuck in Working. No second model voice synthesis for browser actions.
- Silence three legacy unit cancellation tests by mocking their test cue. No change to real Jarvis speech or standalone/manual cue audio.
- Add six new unit tests and update one previous test whose prior expectation that `Could you open YouTube?` should be denied is superseded by approved natural-language support.

## Safety/limitations
- This only extends the explicit YouTube grammar; it is not generic app/URL automation.
- Action failure is shown as a text caption, not spoken in this patch. Future non-visible success/failure should use concise spoken confirmation when appropriate.
- Browser launch accepted does not prove page loaded.
- Existing false-barge-in issue remains out of scope.
- Realtime Mini may fail to choose `test_action` for a natural request; that is still fail-closed.

## Live acceptance
Pending actual Windows live tests; preserve existing patch files/backups, do not commit before acceptance.
