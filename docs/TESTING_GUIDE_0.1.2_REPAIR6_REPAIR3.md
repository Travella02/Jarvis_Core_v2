# Repair6-Repair3 testing instructions

1. Extract patch ZIP into the root of the CURRENT 0.1.2 project (Repair6-Repair2 must already be installed).
2. Apply `python .\apply_0_1_2_repair6_repair3_patch.py`.
3. Focused: `python -m unittest tests.unit.test_0_1_2_repair6_repair3_sleep_evidence tests.unit.test_0_1_2_repair6_repair2_natural_sleep tests.integration.test_0_1_2_repair3_routing_bridge tests.unit.test_0_1_2_repair4_route_latency_observability -v` (23 tests).
4. Full: `python -m unittest discover -s tests -v` (551 tests with one skip).
5. Diagnostics `python -m core.diagnostics`, then `npm run desktop:check`, then `npm run desktop`.

## Live speech sequence
**Test 1:** Wake; `Thanks Jarvis.` → `route=direct`, normal short acknowledgment, MUST stay awake. Repeat twice; verify no `route=sleep`. If route=sleep but `[Jarvis Route Guard]...missing_sleep_evidence`, it should continue, and report that routing is still wrong.
**Test 2:** `Thanks Jarvis, that's all.` → `route=sleep` with literal closure `sleep_evidence`, silent sleep, wake listener remains armed.
**Test 3:** Wake; `Thank you, that helps.` → direct, remain awake.
**Test 4:** `Thanks, Jarvis, one more question: what's 17 times 6?` → direct, answer 102, remain awake.
**Test 5:** `That's everything for now, Jarvis.` → sleep silently.

Compare 5 direct requests with shadow on and off only after sleep acceptance; do not enable speculative audio.
