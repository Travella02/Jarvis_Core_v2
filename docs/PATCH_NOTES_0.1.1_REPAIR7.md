# 0.1.1 Repair7 — Single-Pass Detailed Replies + Scrollable Inline Transcript

Live acceptance of Repair6 confirmed that wake/sleep, concise ordinary replies, detailed replies, and the stable transcript surface all work. Two product issues remained:

1. A detailed request could produce one acknowledgement before the `request_expanded_response` function and then a second acknowledgement when the expanded response began. The result sounded like Jarvis started the same turn twice.
2. The fixed-height inline transcript correctly protected the orb from layout movement, but it automatically followed the newest text and could not be manually scrolled to reread earlier lines without opening the full-screen reader.

## Repair

- The desktop manual-response path no longer exposes the expansion-budget tool. Detailed requests are answered directly in the same Realtime response.
- Desktop responses receive 2048 output tokens of safety headroom for both concise and deliberately detailed turns. The larger ceiling is a guardrail only; ordinary turns still use the compact response instruction and do not become more verbose merely because headroom exists.
- Detailed turns are explicitly told to begin the useful answer immediately, allow at most one natural lead-in, and never say they need to think/wait before restarting the answer.
- The expansion tool remains available by default to older A/B/automatic labs so the provider surface remains backward-compatible while desktop behavior is cleaned up.
- The inline caption viewport is now independently scrollable while keeping the same fixed footprint, so the orb never shifts.
- Auto-follow only owns the transcript while the reader remains near the newest text. Scrolling upward transfers viewport ownership to the user until they return near the bottom, matching the proven V1 smart-follow lesson.
- The existing top fade is disabled while the user is browsing older text so the beginning of the visible passage remains readable.
- The full-screen response reader remains available as an optional larger reading surface.

Realtime Mini, Cedar, WebRTC, wake/sleep, 60-second idle sleep, Core delegation, persona, response brevity, particle presence, and caption character pacing are unchanged.
