# ISSUE-066 — Silent router was opaque and paid a full request-copy cost on direct turns

## Symptom

Repair3 correctly stopped pre-tool speech by making route ownership a silent forced-function response before any audible answer. Live testing then exposed two follow-on problems:

1. console lines were all prefixed by the Electron host as `[Jarvis Core]`, so a user could not tell whether a turn actually entered authoritative Core work or merely passed through the Python host; and
2. even obvious direct turns such as “Which planet is known as the Red Planet?” made the router regenerate a faithful copy of the entire user request under the normal desktop prompt budget before Realtime could answer.

The second issue added avoidable latency to the common direct-conversation path.

## V1 comparison

The included V1 0.3.6 reference already established the architectural rule that metered/provider responses need one explicit owner before provider events are allowed to present results. V1 also repeatedly used ownership-scoped IDs and visible latency telemetry rather than inferring behavior from a generic process prefix. Repair4 keeps that lesson: ownership remains explicit and observable; it does not reintroduce post-hoc suppression or keyword shortcuts.

## Root cause

Repair3's routing response inherited more prompt/budget surface than an internal classifier needed, and `route_jarvis_turn` required a `request` field for every route. Direct and sleep routes do not need that text because the latest user turn is already in Realtime conversation context and no Core backend request is created.

## Repair4

- Keep the pre-speech forced-function ownership gate from Repair3.
- Give the router only its compact routing instructions, not the normal answer prompt.
- Force minimal Realtime reasoning for the routing response only.
- Bound the routing response to 512 output tokens.
- Make `request` optional for `direct` and `sleep`; Core-owned routes still require a concise faithful request and fail closed if it is missing.
- Send only `{status: direct}` back into Realtime for a direct route instead of echoing the user request again.
- Add per-turn route telemetry before the function-call event is forwarded to Core.
- Correlate Core-start/completion logs with the same Realtime function `call_id` and visible desktop turn number.
- Extend latency telemetry with speech-end → route-decision and route-decision → first-audio timings.

## Expected console distinction

Direct turn:

```text
[Jarvis Route] turn=3 | route=direct | owner=realtime | route_ms=... | call_id=...
[Jarvis Direct] turn=3 | realtime-only | call_id=...
```

Core-owned turn:

```text
[Jarvis Route] turn=4 | route=reasoning | owner=core | route_ms=... | call_id=...
[Jarvis Core Call] turn=4 | mode=reasoning | status=started | call_id=...
[Jarvis Core Call] turn=4 | mode=reasoning | status=completed | backend_ms=... | route=... | call_id=...
```

The outer Electron console may still prepend `[Jarvis Core]` to all Python stdout. That prefix identifies the host process, not the intelligence owner of the turn.
