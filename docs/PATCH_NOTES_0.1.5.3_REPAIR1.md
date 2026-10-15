# 0.1.5.3 Repair1 — Browser Action Acknowledgment & Spoken Failures

## Root cause found
The Core host correctly called `BrowserRealtimeRelay.notify_desktop` with a `core_tool_result`, but the relay only forwarded `core_luna_result`. Every browser result therefore vanished before reaching the React UI, causing a 5-second `result_timeout` even on successful YouTube launches.

## Changes
- Forward `core_tool_result` through the existing trusted local WebSocket relay; keep the event-type whitelist narrow.
- Settle matching action results immediately. A verified accepted launch stays silent and returns Ready.
- When Core denies or fails an action, use the existing Core-result voice rendering path to announce a short truthful explanation. Spoken failure must be live-tested; automated tests cannot confirm actual audio output.
- If the action acknowledgment genuinely times out, audibly state only that completion cannot be confirmed. Never replay, claim failure/success, or open another tab automatically.
- Core remains the only execution authority. No newly authorized website or action. The local Relay does not accept an arbitrary message type. The Realtime Mini ordinary/direct conversational path remains unchanged.

## Known boundaries
- Speech requires a functioning Realtime voice channel. If unavailable, the app shows the truthful result in its caption and logs unavailability rather than claiming the alert was spoken.
- Browser-launch accepted is not proof that the target page loaded.
- No change to acoustic interruption, VAD, or unapproved destinations.
- Natural-language YouTube search and contextual 'that' remain experimental; this patch changes results/feedback only.
- No real API/Windows/audio testing was performed by this packaging environment.

Do not commit until Windows live acceptance and cleanup of installer ZIP/backups.
