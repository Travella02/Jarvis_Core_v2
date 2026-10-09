# Testing Guide — 0.1.2-repair5

Do not clean Repair1-Repair5 artifacts or make the final 0.1.2 commit until live acceptance passes.

## Automated checks

Run the focused suite:

```powershell
python -m unittest tests.unit.test_0_1_2_repair5_conversation_trace_and_long_task tests.unit.test_0_1_1_desktop_wake_sleep_contract tests.unit.test_0_1_2_repair4_route_latency_observability tests.integration.test_0_1_2_repair4_route_telemetry tests.unit.test_0_1_2_repair3_pre_speech_routing_gate tests.integration.test_0_1_2_repair3_routing_bridge tests.unit.test_0_1_2_repair2_delegation_preamble_suppression tests.unit.test_0_1_2_repair1_delegation_caption_truthfulness tests.unit.test_0_1_2_intelligence_router tests.integration.test_0_1_2_realtime_delegation_router tests.integration.test_0_1_2_conversation_provider_override tests.integration.test_0_0_9_repair4_realtime_core_delegation tests.unit.test_0_1_1_repair5_manual_response_policy tests.unit.test_0_1_1_repair7_single_pass_detail_scroll -v
```

Expected: `Ran 68 tests ... OK`.

Run the full regression:

```powershell
python -m unittest discover -s tests -v
```

Expected: `Ran 527 tests ... OK (skipped=1)`.

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

## Live test 1 — explicit reasoning route + trace

Say:

**“Jarvis, use your Core to explain why idempotency matters when a client reconnects to a runtime.”**

Expected:

- no filler/preamble speech;
- `[USER SPEECH]` contains the recognized utterance;
- route is `reasoning | owner=core`;
- matching Core Call starts and completes;
- `[JARVIS REPLY] ... source=core` contains the final spoken/displayed answer;
- captions remain complete.

## Live test 2 — background build classification

Say:

**“Jarvis, use your Core to start a background task that builds a project while I’m gone.”**

Expected:

- `[USER SPEECH]` contains the recognized request;
- route is **`long_task | owner=core`**, not `action`;
- Core Call uses `mode=long_task` and reports `status=unavailable` in this build;
- Jarvis gives one truthful unavailable answer;
- `[JARVIS REPLY] ... source=core` matches that answer.

## Live test 3 — direct conversation remains direct

Say:

**“Jarvis, what planet is known as the Red Planet?”**

Expected:

- `[USER SPEECH]` is visible;
- `route=direct | owner=realtime`;
- `[Jarvis Direct] ... realtime-only`;
- no Core Call for this turn;
- `[JARVIS REPLY] ... source=realtime` contains the direct answer.

Record `speech_end->route` and `speech_end->first_audio` for future gate optimization.

## Live test 4 — direct route after Core use is not sticky

Immediately after Test 1 or 2, say:

**“What is 17 times 6?”**

Expected:

- new independent `route=direct` turn;
- no Core Call;
- Jarvis answers `102`;
- labeled USER/JARVIS trace remains aligned to the same turn number.

## Live test 5 — sleep regression

Say:

**“That’s all, Jarvis.”**

Expected: silent lifecycle transition back to the local wake listener. No user-facing Jarvis reply is required.
