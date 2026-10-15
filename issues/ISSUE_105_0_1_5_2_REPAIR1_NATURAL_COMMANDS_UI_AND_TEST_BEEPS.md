# ISSUE 105 — 0.1.5.2 Repair1 action UX and silent tests

Live Windows findings: direct spoken and typed "open YouTube" opened a tab correctly, negation blocked. Polite request "Jarvis can you open YouTube for me" rejected by strict exact-command regex. "Open Google" appropriately blocked, but desktop remained in Working. Three legacy cancellation-timing tests still played actual Windows WAVs under unittest discovery because the silent A/B-launch flag is not global for unittest.

Repair:
- Narrow direct polite YouTube phrasing recognized by Core, maintaining independent committed transcript + strict URL allowlist.
- Distinguish visible browser action completion (silent, Ready) and denied action (caption, Ready) without additional model speech; ignore stale tool results.
- Patch native cue in legacy unit lifecycle tests only; no production sound changes.
- Add regression tests for denied/negated/quoted/compound requests and side effect duplication.

Follow-ups: handle unsupported tools with concise spoken failure when needed, generalized tool result UX, stronger action identity/auth before public release, revisit false mic noise interruptions later.
