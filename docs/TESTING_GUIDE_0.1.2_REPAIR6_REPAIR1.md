# 0.1.2 Repair6-Repair1 — Follow-up testing

1. Extract `Jarvis_Core_v2_0.1.2_repair6_repair1_patch.zip` into the **project root**; it contains a separate `repair6_repair1_files/` directory and doesn't overwrite Repair6's `patch_files/`.
2. Run `python .\apply_0_1_2_repair6_repair1_patch.py`.
3. Run `python -m unittest tests.unit.test_0_1_2_repair6_parallel_shadow -v` (expected: **9 passing**).
4. Run `python -m unittest discover -s tests -v` (expected: **536 tests run, one pre-existing skip**).
5. Run `python -m core.diagnostics` (expected final `Status: ok`).
6. Run `npm run desktop:check`.
7. Launch `npm run desktop`, optionally enabling the existing `JARVIS_PARALLEL_SHADOW_PROBE=1` in local `.env` for shadow-probe live tests. Do not post `.env` contents.

Say the four Repair6 test phrases from `docs/TESTING_GUIDE_0.1.2_REPAIR6.md`. Report `[Jarvis Parallel]` telemetry, any extra audible speech, and actual turn times.

**Never commit or delete patch files/backups until live acceptance.**
