# 0.1.3 Repair13 — Opt-in leading-silence PCM latency trial

**Status:** awaiting Windows live acceptance; no Git commit.

- Adds `mini-overlap-luna-trim` launcher alongside unchanged `mini-overlap-luna` baseline. Both keep real Core/Luna and dry-run actions. No Decisions shadow in either Repair13 A/B arm.
- Opt-in AudioWorklet change discards only *leading* zero/near-zero provider PCM, preserving an 8 ms pre-roll and all subsequent audio; start buffer remains 45 ms. Can reduce artificially queued silent startup latency, but size of real benefit is **unknown** until measured on user hardware.
- Independent PCM onset/buffer milestones and timing relative to Core authorization and first audible worklet output. Read-only logging only.
- Repairs previously absent `underflow` argument at `StreamingPcmGate.create` call; the first underrun is logged without throwing an exception.
- Keeps private mute gate, per-turn epochs, verified transcript, authority decisions, cancellation, wake, sleep, interruption and Luna provider unchanged.
- Adds `scripts/repair13_latency_report.py`, regression tests and sample-level simulated AudioWorklet tests.

See `issues/ISSUE_091_0_1_3_REPAIR13_PCM_LEADING_SILENCE_LATENCY.md` and `docs/TESTING_GUIDE_0.1.3_REPAIR13.md`.
