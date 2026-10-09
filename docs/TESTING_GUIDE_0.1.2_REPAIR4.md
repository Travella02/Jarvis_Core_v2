# Testing Guide — 0.1.2-repair4

Do not clean patch artifacts or make the final 0.1.2 commit until live acceptance passes.

## Automated checks

Run the focused suite:

```powershell
python -m unittest tests.unit.test_0_1_2_repair4_route_latency_observability tests.integration.test_0_1_2_repair4_route_telemetry tests.unit.test_0_1_2_repair3_pre_speech_routing_gate tests.integration.test_0_1_2_repair3_routing_bridge tests.unit.test_0_1_2_repair2_delegation_preamble_suppression tests.unit.test_0_1_2_repair1_delegation_caption_truthfulness tests.unit.test_0_1_2_intelligence_router tests.integration.test_0_1_2_realtime_delegation_router tests.integration.test_0_1_2_conversation_provider_override tests.integration.test_0_0_9_repair4_realtime_core_delegation tests.unit.test_0_1_1_repair5_manual_response_policy tests.unit.test_0_1_1_repair7_single_pass_detail_scroll -v
```

Expected: `Ran 55 tests ... OK`.

Run the full regression:

```powershell
python -m unittest discover -s tests -v
```

Expected: `Ran 521 tests ... OK (skipped=1)`.

Then:

```powershell
python -m core.diagnostics
```

Expected final line: `Status: ok`.

Then:

```powershell
npm run desktop:check
```

Then launch:

```powershell
npm run desktop
```

## Live test 1 — explicit reasoning/Core route

Say:

**“Jarvis, use your Core to explain why idempotency matters when a client reconnects to a runtime.”**

Expected behavior:

- no audible routing/preamble speech;
- one complete useful answer;
- captions remain complete;
- terminal contains `route=reasoning | owner=core`;
- the same turn/call is followed by `[Jarvis Core Call] ... status=started` and then a terminal status such as `completed`.

## Live test 2 — unsupported background action

Say:

**“Jarvis, use your Core to start a background task that builds a project while I’m gone.”**

Expected behavior:

- no “I'll start it” acknowledgement;
- one truthful unavailable response;
- terminal contains `route=long_task | owner=core`;
- a matching Core Call reports `status=unavailable`.

## Live test 3 — simple direct question and gate latency

Say:

**“Jarvis, what planet is known as the Red Planet?”**

Expected behavior:

- answer is direct (normally “Mars”);
- no Core Call line for that turn;
- terminal contains `route=direct | owner=realtime` and `[Jarvis Direct] ... realtime-only`;
- the routing response budget should be very small compared with Repair3 because direct routes no longer echo the request;
- record `speech_end->route` and `speech_end->first_audio` from `[Desktop latency]` so Repair3 vs Repair4 can be compared.

## Live test 4 — ordinary direct conversation after prior Core work

Immediately after a Core-owned test, say:

**“Jarvis, tell me a quick joke.”**

Expected behavior:

- terminal shows a new independent `route=direct` turn;
- there is no Core Call for that turn;
- this proves Core ownership does not stay sticky after a previous delegation.

## Live test 5 — sleep regression

Say:

**“That’s all, Jarvis.”**

Expected behavior: silent transition back to sleeping/wake-listener state. The route line should identify the lifecycle route rather than Core work.
