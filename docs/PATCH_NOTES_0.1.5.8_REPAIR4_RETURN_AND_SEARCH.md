# 0.1.5.8 Repair 4 — natural return-and-search

## Problem
Live tests after Repair 3 succeeded for straightforward browser navigation but rejected natural *return to background YouTube tab and search* commands with `unverified_user_intent` or `unverified_arguments`. This is action planning/argument validation, not evidence that target-tab navigation itself failed.

## Scope
- Clarify the Realtime Mini tool description: a single `browser_action` of `intent=search` with an explicit domain and user-grounded query represents a same-site return+search, without a second model call.
- If the model instead proposes `open` or `select_tab` with a non-empty query, normalize to `search` ONLY when the independently confirmed current-turn speech explicitly requests a search of that same site and provides the significant search terms. The normal Core gateway still authorizes the action. Never infer a missing query.
- Keep Repair 3 guarded navigation, tab identity and extension authorization entirely unchanged. No modification to extension files, wake/sleep, STT/TTS, ordinary conversation route, app discovery/history or memory.
- Return to an existing tab remains unavailable without an authorized, connected Chrome/Edge extension. Other browsers are not silently controlled. A disconnected browser still uses the OS default (new-tab handoff) and does not claim tab reuse.
- Core denies negated, hypothetical or unsupported browser commands. No implicit multi-action execution.

## Baseline and validation
This installer targets the exact known Repair 3 code hashes. STOP on mismatches; send a fresh clean checkpoint for reconciliation, rather than forcing replacement.
Offline regression: 35 passing browser tests, including 9 new tests for background-tab reuse and failure safeguards. A fresh Windows live test and the full repository suite remain required before committing.

## V1 reference
V1's planner used real browser tab IDs and its runtime selected grounded tab identities from browser state. Repair 3 retained that principle, while this repair addresses the Mini proposal format that prevented some natural requests from reaching it.
