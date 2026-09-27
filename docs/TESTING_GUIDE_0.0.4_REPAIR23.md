# Testing Guide — 0.0.4 Repair23

From the Jarvis Core v2 project root:

```powershell
python apply_0_0_4_repair23_candidate.py
python -m unittest tests.unit.test_qwen3_streaming_candidate -v
python -m unittest tests.unit.test_qwen3_streaming_resident_benchmark -v
python -m apps.qwen_streaming_resident_benchmark --voice-profile tanner-test
```

Expected automated checks:
- Existing Repair22 candidate tests: 3/3 OK.
- Repair23 resident benchmark tests: 3/3 OK.

For the live benchmark, the first warmup may still take tens of seconds because
that is where compilation is intentionally allowed to happen. The important
values are the three measured `RESIDENT_RUN_SUMMARY` entries and the final:

`RESIDENT_BENCHMARK_SUMMARY=...`

Do not commit yet. This benchmark decides whether the next repair should
integrate a resident streaming provider or continue optimizing the candidate.
