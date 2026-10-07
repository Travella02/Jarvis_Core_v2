# 0.1.2 — Intelligence Router & Core Delegation Testing Guide

Do not commit until automated tests and live delegation acceptance pass.

## Focused tests

```powershell
python -m unittest `
  tests.unit.test_0_1_2_intelligence_router `
  tests.integration.test_0_1_2_realtime_delegation_router `
  tests.integration.test_0_1_2_conversation_provider_override `
  tests.integration.test_0_0_9_repair4_realtime_core_delegation `
  tests.unit.test_0_0_6_provider_router -v
```

## Full regression

```powershell
python -m unittest discover -s tests -v
```

## Diagnostics

```powershell
python -m core.diagnostics
npm run desktop:check
```

Expected diagnostics includes `delegation=ready` and ends with `Status: ok`.

## Live default-route test

Leave `JARVIS_OPENAI_STRONG_MODEL` blank and run:

```powershell
npm run desktop
```

Wake Jarvis and say:

**“Jarvis, use your Core to explain why idempotency matters when a client reconnects to a runtime.”**

Expected: Core delegation completes on the default route and Realtime presents the result naturally.

## Optional strong-route test

Only after an exact stronger model ID has been validated for the account, set it in `.env`:

```text
JARVIS_OPENAI_STRONG_MODEL=<validated model id>
JARVIS_OPENAI_STRONG_REASONING_EFFORT=low
```

Restart Jarvis and say:

**“Jarvis, use your Core to analyze this architecture, compare the tradeoffs, debug the likely root cause, and design a safer multi-step migration plan.”**

Expected: Core selects the `strong` route. Realtime itself must never name/select that route in its function arguments.

## Fail-closed capability test

Say:

**“Jarvis, use your Core to start a background task that builds a project while I’m gone.”**

Until durable tasks are implemented, expected behavior is a truthful unavailable result. Jarvis must not claim the task started.

Similarly, unimplemented memory/action/current-data capability requests must fail truthfully rather than fall through to ordinary model reasoning.
