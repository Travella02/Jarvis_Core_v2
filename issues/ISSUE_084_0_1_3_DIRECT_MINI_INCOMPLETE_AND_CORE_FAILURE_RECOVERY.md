# ISSUE 084 — Recoverable Mini truncation must not take Jarvis OFFLINE

Status: Repair6 candidate — live acceptance pending.

## Reproduction and root cause

In `mini-overlap-luna-cancel-test`, a direct request to explain training an AI
reached the speculative audio response `max_output_tokens=1024`, with
`status=incomplete` and `reason=max_output_tokens`. The desktop's overlap branch
aborted the PCM gate with an error reason and called
`setStateSafely('error','Candidate answer incomplete')`. The UI shows OFFLINE
whenever JarvisState is ERROR, blocking its input despite a still-connected
Realtime session. Repair4 protected `core_luna_voice`, not `overlap_candidate`.

Separately, after an interrupted/failed Luna turn, Core can hold a terminal
ERROR state after the old active trace clears. The next authorized user request
then raises `RuntimeError` before calling Luna. Recover only after the prior
turn has fully ended; keep sleeping, busy and active Core protected.

## Repair6 scope

- Add an explicitly guarded direct-candidate fallback: abort private audio,
  preserve partial transcript with a truthful interruption note, return UI to
  IDLE, and report `phase=recoverable_incomplete`; do not fake completion.
- Apply the same fallback to direct-response PCM/transport errors when a direct
  decision is already authorized; keep true connection/session failures distinct.
- Do not increase the 1024-token speculative cap or change Jarvis personality,
  response-length policy, the clean audio renderer, or Decisions routing.
- Allow a new authorized Core delegation to recover a previous terminal error
  *only* when no active trace remains. No silent provider retry and no user
  actions enabled.
- Improve `RuntimeError` category logging (busy vs not ready).

## Acceptance

1. All focused/full tests, diagnostics, desktop check pass on Windows.
2. Direct long response that reaches output budget leaves Jarvis awake and
   usable; UI offers readable partial answer and truthful retry instruction.
3. Subsequent direct request succeeds without restarting application.
4. A failed delegated Luna request can be followed by a successful new request.
5. Sleep/wake and Luna natural voice/cancellation remain unaffected.

Do not clean or commit before live acceptance.
