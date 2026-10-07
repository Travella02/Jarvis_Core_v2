# ISSUE 063 — Delegation Preamble Contradiction & Caption Truncation

## Live symptom

During 0.1.2 acceptance testing, Realtime spoke pre-tool phrases such as a thinking/explanation lead-in and an announcement that a background project was being prepared. The second case contradicted Core's later authoritative result that durable background tasks are not implemented.

At the same time, the desktop text stopped partway through those spoken phrases even though Cedar continued speaking.

## Root cause

Two independent boundaries were too permissive:

1. The Realtime prompt allowed natural work acknowledgements before delegation, so a model could narrate intended progress before the capability result existed.
2. The desktop called `clearCaptionPacing(false)` at the function-call boundary and again when a function-call response reached `response.done`. That cleared the generated transcript source while already-buffered audio could still be playing.

## Repair

0.1.2-repair1 makes Core delegation tool-first and silent until the function result, strengthens status-truthfulness rules, and finalizes any already-generated caption at the function-call boundary rather than discarding it.

## V1 comparison

The V1 0.3.6 reference already carried two relevant hard-earned lessons: stale/provider lifecycle events must not truncate the response currently being presented, and external/action success must not be claimed without a confirming tool result. Repair1 ports those invariants without importing V1's larger presentation stack.
