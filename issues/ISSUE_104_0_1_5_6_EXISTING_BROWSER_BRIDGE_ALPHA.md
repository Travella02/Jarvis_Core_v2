# ISSUE 104 — Default-browser tab reuse and verified browser controls

**Status:** Candidate1 pending Windows live acceptance.

## Observed problem

0.1.5.5 opened an OS-default browser tab successfully, but subsequent YouTube searches created additional tabs. Media controls in a separate Playwright browser were not useful to ordinary users and could report unsupported actions. User explicitly requested modular control of their installed default browser, leveraging established v1 behavior.

## Remedy

Reintroduced a narrow, Core-verified bridge to the v1 Chrome/Edge extension (read-only reference source), with session-independent connection, tab reuse by exact hostname, media state verification and OS-default fallback. No v1 runtime provider/cost/permission modules were copied. Failures are not masked as success.

## Risk and future action

Extension permission review, robust secret pairing, browser adapter detection/Firefox, user-prompted site permissions, cancellation fences, tab ownership across browser instances, and full browser navigation/semantic DOM plan are all **deferred**, not silently accepted. Keep opt-in profile only, no production release claim.
