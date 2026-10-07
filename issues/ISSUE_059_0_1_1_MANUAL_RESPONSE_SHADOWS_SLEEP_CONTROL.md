# ISSUE 059 — 0.1.1 Manual response policy can shadow sleep lifecycle control

## Symptom

After Repair5 moved desktop turns to manual `response.create`, an explicit sleep phrase could produce spoken text such as “Got it—signing off…” and leave Jarvis awake rather than invoking `sleep_jarvis`.

## Cause

The response-specific compact formatting instructions were strong enough to dominate the turn but did not restate lifecycle/tool control. The session-level sleep policy remained present, but it was not reliable enough once each turn had its own response instructions.

## Fix

Response-specific ordinary-turn instructions now place lifecycle/tool behavior ahead of spoken formatting. Clear sleep intent must call `sleep_jarvis` as the initial and only output, with no spoken acknowledgement.

## Regression rule

Any future per-turn response policy must preserve lifecycle and authoritative Core tool-routing instructions before style/length constraints.
