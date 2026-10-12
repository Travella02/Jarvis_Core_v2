# 0.1.2 Repair6-Repair2 — Live test guide

1. Extract `Jarvis_Core_v2_0.1.2_repair6_repair2_patch.zip` into the **project root**, alongside existing Repair6 artifacts. This patch has its own `repair6_repair2_files` folder and apply script.
2. Apply with `python .\apply_0_1_2_repair6_repair2_patch.py`.
3. Test focused: `python -m unittest tests.unit.test_0_1_2_repair6_repair2_natural_sleep tests.unit.test_0_1_2_repair6_parallel_shadow tests.integration.test_0_1_2_repair3_routing_bridge -v` (18 tests).
4. Full: `python -m unittest discover -s tests -v` (541 total, one existing skip).
5. Diagnostics: `python -m core.diagnostics` (Status: ok). Desktop: `npm run desktop:check`.
6. Restart Jarvis with `npm run desktop`, shadow enabled if preferred for original Repair6 testing.

**Speech test 1:** "Jarvis, what planet is known as the Red Planet?" => `route=direct`, one audible answer.
**Speech test 2:** "Thanks Jarvis, that's all." => `route=sleep`, silent lifecycle transition, local wake rearmed. DO NOT require exact word order in general.
**Speech test 3:** Wake and say "Thanks Jarvis." => ordinary friendly `route=direct` acceptable, must NOT sleep solely due to gratitude.
**Speech test 4:** "Thanks, Jarvis, one more question: what's 17 times 6?" => direct answer 102, no sleep.

**Shadow A/B:** Restart Jarvis with `JARVIS_PARALLEL_SHADOW_PROBE=0`, ask Mars 5 times and collect `speech_end->first_audio`. Repeat 5 times after another restart with shadow=1, under similar network conditions. Compare medians and collect `[Jarvis Parallel]` entries. No user-facing answers are expected from probes in either condition. Do not share `.env` contents.

These tests validate routing and timing only. They do not claim speculative voice buffering is installed.
