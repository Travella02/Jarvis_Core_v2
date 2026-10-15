# Browser Bridge 0.1.5.6 — STT Search-Verb Authorization Mismatch

## Live reproduction
The user said "Search YouTube for Sidemen". The independently confirmed STT transcript logged
`Sirch YouTube for Sidemen.` GPT Realtime Mini proposed the browser search action correctly,
but Core refused with `code=unverified_user_intent`, before calling the connected browser adapter.
Opening YouTube just beforehand succeeded.

## Root cause
`core/tools/managed_browser.py::trusted_intent` required an exact regex match of the search
verb. `sirch` preserves search's consonant sounds but does not match `search` or `find`.

## Repair boundary
Only the search authorization evidence path has changed; the model still chooses the action.
A conservatively normalized consonant signature allows a search-like verb near a recognized
search site. The requested query tokens must appear in the same current-turn user transcript.
Negation, hypothetical, compound-action safety, host restrictions, turn binding and idempotency
remain in force. No hardcoded special case for Sidemen or a particular user phrase.

## Acceptance
Automated tests must remain silent, the ordinary Realtime path remain fast, and a live connected
browser must reuse the YouTube tab after hearing `Sirch YouTube for Sidemen`.
The patch does not expand browser site support, add arbitrary video clicking, or disable guards.
