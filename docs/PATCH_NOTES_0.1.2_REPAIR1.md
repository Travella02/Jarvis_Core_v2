# 0.1.2-repair1 — Delegation Truthfulness & Caption Continuity

## Why this repair exists

Live 0.1.2 testing exposed two related presentation failures around Core delegation:

- Realtime could speak a natural-sounding preamble before the `delegate_to_jarvis_core` function call. For an unsupported background-task request, that preamble could imply the task was about to start before Core returned the authoritative `unavailable` result, creating a contradiction.
- The desktop caption controller cleared its generated transcript buffer when a function call completed. If Cedar had already queued spoken preamble audio, the visible text could stop mid-sentence while the audio continued.

## Fixed

- A Core delegation function call is now required to be the initial output for that response. Realtime must not speak an acknowledgement, plan, or filler before the delegation call.
- Realtime may not say or imply that an action, task, search, lookup, or other delegated capability is starting, queued, possible, or complete until Core confirms that state.
- The desktop `WORKING` state acts as the immediate acknowledgement while Core is pending; the spoken response resumes from the authoritative Core result.
- Core-result presentation now explicitly checks function-result status. `unavailable`, `failed`, `cancelled`, and `superseded` outcomes may not be narrated as successful progress.
- If a provider ever emits spoken audio before a function call despite the prompt, the desktop now finalizes the full generated caption rather than discarding its remaining text at the function-call boundary.
- The same caption-preservation rule is applied when the tool-call response reaches `response.done`.

## V1 regression lessons reused

The included read-only V1 0.3.6 reference was inspected before this repair. Two prior V1 rules were deliberately reused:

- provider responses must be correlated with the output they actually own so stale/provider lifecycle events do not truncate or mutate the visible response;
- action success must never be claimed without an authoritative tool result.

Repair1 keeps the v2 architecture simpler than V1 while preserving those two invariants.

## Scope

This repair does **not** implement durable background tasks, actions, current-data lookup, or Memory 2.0. Those capability slots remain fail-closed exactly as 0.1.2 intended.
