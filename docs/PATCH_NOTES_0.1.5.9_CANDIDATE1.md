# Jarvis Core v2 — 0.1.5.9 Candidate 1 — Verified YouTube Result Selection

## What changed
- A connected, authorized Chrome/Edge browser bridge can read a fresh, bounded page snapshot **only inside Core** to select the explicitly numbered video on an active YouTube results page. It deduplicates watch links by video ID, checks domain/scheme/ID, and navigates to a canonical `https://www.youtube.com/watch?v=...` URL in the same tab via the existing guarded navigation command.
- New `select_result` Mini intent with explicit ordinal `value` (1-10) and `site=current`; Core independently checks the actual spoken ordinal and immediate request. Negations, hypotheticals, compound actions, missing/ambiguous results and focus races fail closed. No arbitrary DOM click/typing or unrestricted agentic browsing is enabled.
- New `fullscreen` and `exit_fullscreen` Mini intents routed through the existing audited media-fullscreen worker. Existing pause, resume, mute, unmute and explicit-percentage volume stay intact.
- Core browser-command allowlist adds only read-only `snapshot` and existing `media_fullscreen`; the browser extension is unchanged. Ordinary Realtime Mini voice/chat route does not do new snapshot work or call Luna. Do not install a new extension for this candidate.
- Correctly reports successful result navigation as a page open, not verified playback: autoplay is controlled by browser/site policy. Underlying browser worker may attempt native fullscreen; Core requires its verified result.

## Known limits
- First slice supports **numbered YouTube video results only**, with an already-connected Chrome/Edge Jarvis extension. It does not claim arbitrary site UI control, ad detection, automatic YouTube autoplay, result titles not included in the extension snapshot, or support for browsers lacking the authorized extension.
- The YouTube page must show `/results?search_query=...` in the active tab. If the tab changed or the selected ordinal is not in the snapshot, Jarvis must audibly report the failure rather than click an ungrounded element.
- Browser-result actions are slower than normal conversation because they must read and verify real browser state. The regular short-answer response latency path is unchanged.

## Review and commit
Offline suite in reconstructed 0.1.5.8 Repair4 source: 807 tests OK, one skipped. Windows desktop/browser live smoke tests **not yet executed**. Apply only to the exact Repair4 checkpoint hashes below. Do not commit until live tests pass; delete the installer, patch_payload directory and .patch_backups directory as usual, and then commit.
