# ISSUE 064 — Delegation Preamble Still Leaked After Repair1

## Live symptom

Repair1 live acceptance still produced pre-tool speech:

- “let me pull in the Core on this and respond clearly” before a reasoning delegation; and
- “okay let me get that started for you” before a background-task request that Core later rejected as unavailable.

The first preamble appeared abruptly as text rather than pacing with speech. The second preamble text could be cut off or disappear when the authoritative result response began.

## Root cause

Repair1 relied on prompt compliance for the most important boundary: it told Realtime that delegation must be tool-first, but it still allowed provider-generated audio to reach the speaker until the tool event completed. A probabilistic model instruction cannot be the only enforcement mechanism for action truthfulness or private internal-routing narration.

Repair1 also preserved the pre-tool transcript at the function-call boundary. That prevented truncation but made internal narration visible instead of eliminating it.

## Repair

Repair2 makes the client enforce a response-ownership boundary:

1. As soon as the current response exposes a `delegate_to_jarvis_core` function-call output item, the response ID is marked suppressed.
2. Remote audio is muted and the provider output buffer is cleared immediately.
3. Transcript and stale output-buffer events for that response ID are ignored.
4. At `response.done`, any generated assistant message item associated with that suppressed response is deleted from Realtime history.
5. The next response created from the authoritative function result is a different response ID and restores normal audio/caption streaming.

The prompt is also tightened so internal architecture names are never narrated during ordinary task fulfillment.

## V1 comparison

V1 already learned to bind provider lifecycle events and audio ownership to response IDs, and to suppress responses that should never reach the user. Repair2 ports that invariant directly instead of trying to solve an ownership problem with prompt wording alone.
