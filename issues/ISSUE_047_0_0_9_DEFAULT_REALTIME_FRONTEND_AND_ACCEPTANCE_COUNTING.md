# ISSUE 047 — Final 0.0.9 frontend selection and acceptance counting

## Problem

The A/B milestone had proven multiple voice frontends but still defaulted configuration/documentation to the earlier GPT-Live experiment. The Realtime lab also used raw `response.done` count as its completion gate, which can count tool/function-call responses separately from real user turns and can close the session before the final audible sentence finishes. It also prewarmed Luna even when no Core delegation occurred.

## Resolution

Repair6 selects Realtime 2.1 Mini + WebRTC as the current default conversational frontend while preserving all alternatives. Acceptance now tracks captured user speech turns and waits for the final completed non-function response with no pending Core delegation. Core backend warmup becomes opt-in and the final playout grace is increased.

## Authority invariant

The selection is replaceable. Realtime Mini remains a conversational provider; Jarvis Core owns memory, tools, permissions, tasks, state, and backend routing.
