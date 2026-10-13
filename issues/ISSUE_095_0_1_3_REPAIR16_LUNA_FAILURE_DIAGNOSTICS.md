# Issue 095 — Core/Luna failure reason hidden

## Observed (live)
Mini selects `ask_luna`, Core starts, then `status=failed` after ~5.4 seconds and Jarvis speaks a generic 61-character failure. No HTTP code, selected route or provider error class reached the terminal. A previous completed delegation also appeared to speak instructions rather than the actual analysis.

## Repair
Log whitelisted failure metadata already present in the Core `DelegationResult.detail`, enrich OpenAI SDK error categories without exposing raw exception string/body, and test privacy, failure, success parity. Root cause pending Windows live repeat.

## Acceptance
Use the new diagnostic line to identify and fix the underlying issue in a separate verified patch. Do not count this logging improvement as successful Core/Luna delegation.
