# ISSUE-067 — Route telemetry lacked conversation text and background work was classified as generic action

## Symptoms

Repair4 finally made route ownership visible, but live debugging still required manually matching spoken questions to anonymous turn numbers. The same live run also showed:

```text
route=action | owner=core
```

for a request whose defining requirement was to continue building a project in the background while the user was away.

The result still failed safely because the action capability was unavailable, but the route was semantically wrong and would become important once both action and durable-task handlers exist.

## Root causes

1. The terminal emitted route, Core call, response budget, and latency telemetry but no accepted user transcript or final Jarvis response text.
2. The router described `action` and `long_task` as peer labels without an explicit precedence rule when a request satisfied both.

## Repair5

- Add explicit `[USER SPEECH]` and `[JARVIS REPLY]` terminal records with turn correlation and source labels.
- Preserve exact typed/wake-preserved text without an extra transcription call.
- For awake voice, enable an optional asynchronous Realtime input transcription stream for development trace only.
- Keep tracing configurable/disableable because provider transcription is separate observability, not response authority.
- Define `action` as immediate interaction-scoped external work.
- Define `long_task` as durable/background/autonomous/queued work.
- Add an explicit rule that background/durable execution wins over generic action classification.

## Why Repair5 does not replace the gate

Repair3/4's pre-speech gate is currently the only proven mechanism in V2 that structurally prevents the Realtime frontend from leaking an acknowledgement before Core truth is known. Repair5 avoids destabilizing it.

A later latency milestone should test a high-confidence local/direct fast path or another non-sequential ownership mechanism. A 50–100 ms *cloud* routing hop is not a safe latency budget to assume because network RTT, inference, and event delivery alone can exceed it. The long-term target should therefore be to remove the sequential cloud hop from obvious direct conversation rather than merely shrinking its token ceiling.
