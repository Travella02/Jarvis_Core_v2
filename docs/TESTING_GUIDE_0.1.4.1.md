# Jarvis Core v2 — 0.1.4.1 Delegation Guidance A/B

**Status: experimental. No cleanup/commit until live acceptance.** The production-like 0.1.3 accepted behavior is unchanged in the baseline launch. `mini-overlap-luna-trim-guided` adds only a short routing rubric to the existing Mini silent decision; there is no extra API/classifier call, no forced routing, no permission change, and no new model.

## Install and automated checks

1. Extract the ZIP to the project root and run `python .\apply_0_1_4_1_patch.py` from your venv.
2. `python -m unittest tests.unit.test_0_1_4_1_routing_guidance -v`
3. `python -m unittest discover -s tests -v`
4. `python -m core.diagnostics`
5. `npm run desktop:check`
6. `npm run desktop:build`

Do not start a live run if any test fails.

## Live test: two arms, same input order

One run for each launcher below; close Jarvis fully between arms. This tests intent-appropriate **route choice** and the actual Core result, not just tool selection. Use the same natural speaking pace and let Jarvis finish completely before the next prompt. No extra conversations between test prompts.

* **Baseline A:** `python .\scripts\realtime_ab.py mini-overlap-luna-trim`
* **Guided B:** `python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided`

For each run, start PowerShell logging **before** launching Jarvis so the output can be analyzed locally. Write to the ignored `.runtime` directory. Use these in separate PowerShell commands:

```
New-Item -ItemType Directory -Path .\.runtime\benchmarks -Force | Out-Null
Start-Transcript -Path .\.runtime\benchmarks\0141_baseline.log -Force
python .\scripts\realtime_ab.py mini-overlap-luna-trim
Stop-Transcript
```

For guided mode repeat `Start-Transcript` and `Stop-Transcript` with `0141_guided.log` and use the guided launcher.

### Wake and prompts

Wake-only phrase *first*: **"Hey Jarvis."** It should acknowledge you. This is **turn 1**, not part of the 12-question benchmark.

Read the following twelve questions in this exact order, pausing until Jarvis has completed each answer. Do not insert or repeat a question. Model route labels below are *test expectations*, not certainties, and wrong transcriptions make the order-based report invalid.

| # | Question | Expected route |
|---|---|---|
| 1 | How are you doing today? | Mini direct |
| 2 | What is seventeen times twenty-three? | Mini direct |
| 3 | Compare local-first and cloud-first AI assistants for a real product, including privacy, latency, costs, and reliability, then recommend one and explain why. | Core/Luna |
| 4 | What planet is called the Red Planet? | Mini direct |
| 5 | Design a secure assistant memory system synchronized across devices, covering encryption, recovery, retention, deletion, and device revocation. | Core/Luna |
| 6 | What's the capital of France? | Mini direct |
| 7 | Compare three production architectures for a multi-tenant assistant with authorization, isolation, retry design, and audit logs; recommend one. | Core/Luna |
| 8 | In one sentence, what does caching mean? | Mini direct |
| 9 | Design a robust cancellation system for a voice assistant so stale asynchronous Core results can never speak after a new request; describe test cases. | Core/Luna |
| 10 | What is nine times eight? | Mini direct |
| 11 | Compare three recovery strategies for distributed background jobs, accounting for idempotency, observability, and cost, and choose the best for a small SaaS. | Core/Luna |
| 12 | Give me one quick fact about space. | Mini direct |

After question 12 say **"That's all, Jarvis"** and verify silent sleep. Do not count sleep in route accuracy.

## Local report (no transcripts printed)

```
python .\scripts\repair_0_1_4_1_routing_report.py .\.runtime\benchmarks\0141_baseline.log .\.runtime\benchmarks\0141_guided.log
```

**Important:** The report expects questions 1–12 to be turns 2–13. If ASR missed a command, if Jarvis never woke, or if you repeated any utterance, the per-question alignment can be wrong. Check turn IDs in your logs and **do not interpret mismatched results as accuracy**. Reports never print raw transcript text; the `.log` files *do* contain your utterances and should remain local/ignored and private. Share the summary and any relevant non-sensitive log lines, not API keys or arbitrary full transcripts.

Compare routing choice matches, actual `phase=result | status=completed` after Core, median direct first-audio and route timing. Five correct escalations **plus six fast direct responses**, stable wake/sleep, cancellation authorization, and no audio regression matter more than route-count accuracy alone. Guided mode might be slower due to longer instructions: this is why it is opt-in. Do not declare it better from one small run. For a statistically meaningful latency test, repeat >=20 already-awake direct turns per arm on additional sessions.

## Existing regression (normal trimmed-PCM arm)

These five standard phrases must remain intact (perform after the matched 12-turn runs):

1. "Hey Jarvis, what planet is called the Red Planet?" — wakes and answers Mars without an extra greeting.
2. "Go to sleep, Jarvis." — sleeps silently.
3. "Jarvis, what's seventeen times six?" — wakes and answers 102.
4. "Thanks, Jarvis." — stays awake with a natural acknowledgment.
5. "Thanks Jarvis, that's all." — sleeps silently.

Also ensure external action requests are still Core-authorized and dry-run only; no files may be created. The 8-second test-only Luna cue remains available in its old launch mode, unchanged.

## Acceptance rules

* Automated full suite, diagnostics, desktop checks, and live regression pass.
* Record both arms and review quality of replies and reasons for delegation.
* **Reject guided arm** if it misroutes simple asks, increases direct median latency materially, creates new errors, bypasses Core, or makes voice less natural. Keep baseline.
* Keep patch files, installer, and `.patch_backups` until acceptance; stage only persistent source/tests/docs when accepted.
