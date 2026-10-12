# Gate-free conversation-only benchmark

Run the patch installer, then `python -m unittest tests.unit.test_0_1_2_repair6_repair5_gate_free_ab -v`, the full unittest suite, diagnostics and `npm run desktop:check`.

In separate sessions run:

```
python .\scripts\realtime_ab.py mini-fast
python .\scripts\realtime_ab.py full-fast
```

Repeat the same direct prompts in both models, at least twice, recording latency, exact answer and session cost:

1. "Jarvis, what planet is known as the Red Planet?" — Mars.
2. "What is seventeen times six?" — 102.
3. "Explain idempotency in two sentences." — avoids duplicate side effects on retries.
4. "Compare optimistic and pessimistic concurrency for a multi-user app." — clear valid tradeoffs.
5. "How's your day going, Jarvis?" — natural conversational tone.

**DO NOT ask actions, Core delegation, current-data requests, memory lookup, or voice sleep during fast runs.** Those capabilities are deliberately disabled here. Close the app manually to end a run. `route=none` and `route=direct_no_gate` are expected. Compare `[Desktop latency]`, `[Jarvis A/B Turn]` and `[Jarvis A/B Session]` to the earlier `mini` and `full` safe routed tests.

This validates direct conversational quality/speed, not the full tool-capable gate-free architecture. The normal routed launcher remains available and unchanged.
