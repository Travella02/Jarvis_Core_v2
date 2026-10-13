# 0.1.3 Repair12 — Decisions + REAL Core/Luna routing A/B (Windows)

## Do not change production routing yet

This patch adds a matched **experimental** comparison. Both arms still use GPT-Realtime-2.1 Mini and real Core/Luna reasoning via the existing authoritative route. In the second arm, the Decisions API runs **in parallel but as a read-only observer**. It **does not** authorize earlier audio, tools, or sleep. The Decisions API incurs an additional billable input request for each valid observed utterance. The comparison measures possible routing headroom, not a demonstrated audio speedup.

## Apply

1. **Fully stop** any running Jarvis desktop/Core and close Electron.
2. Extract the Repair12 patch ZIP **into the `Jarvis_Core_v2` project root**, preserving the `patch_files` folder and the root apply script.
3. Run the root `apply_0_1_3_repair12_patch.py` script from the project's activated Python virtual environment. The script rejects unknown/modified baseline files, creates timestamped `.patch_backups`, installs files, and leaves backups/patch files in place until acceptance.
4. Run the Repair12 unit tests, then the full regression suite, Core diagnostics and `npm run desktop:check`.
5. **Do not commit or clean temporary patch artifacts** until Windows live A/B passes and the user explicitly accepts.

## Paired live A/B

Open PowerShell in the project root with `.venv` active. Stop both Core and Electron between launches. For each arm, use a PowerShell transcript if convenient, saving under `.runtime` so generated logs are ignored by Git. If `Start-Transcript` on a given Windows terminal does not capture native process output, copy the terminal text to a `.log` file manually. Avoid uploading unredacted private transcripts/secrets.

**Arm A: Original Mini router plus REAL Core/Luna**

`python .\scripts\realtime_ab.py mini-overlap-luna`

**Arm B: Same Mini router + REAL Core/Luna, plus Decisions shadow**

`python .\scripts\realtime_ab.py mini-overlap-luna-decisions-shadow`

Keep microphone, headphones, network, room volume and testing pace comparable. Don't run both at once. The launcher prints `decisions_shadow=off | core_luna=on` versus `decisions_shadow=on | core_luna=on`. Both must show `ACTIONS DRY RUN`. In Arm A no `[Jarvis Repair12 A/B]` lines appear; in Arm B the observational metric prints per completed direct spoken turn.

### Five standard wake/sleep phrases (once per arm)

1. While asleep: **"Hey Jarvis, what planet is known as the Red Planet?"** — wake and answer.
2. While awake: **"Go to sleep, Jarvis."** — sleep without unsolicited speech.
3. While asleep: **"Jarvis, what's seventeen times six?"** — wake and answer 102.
4. While awake: **"Thanks, Jarvis."** — natural response without sleep.
5. While awake: **"Thanks Jarvis, that's all."** — verified compound sleep, no spoken answer.

### Already-awake direct latency measurements

After waking, speak 20 or more simple, repeatable questions **in each arm**. Repeat exactly the same questions in a comparable order, or alternate the order to balance warmup effects. Examples: "What is two times six?", "Which planet is called the Red Planet?", "What's the capital of France?", "What is nine times eight?", "Tell me a quick fact about space." Avoid very short sign-offs in the 20 direct sample and keep wake turns out of the latency comparison.

### Safety/delegation checks (record separately)

- "Explain the tradeoffs in a complex distributed job queue design." — select real Core/Luna, wait for a single voiced verified answer.
- "Open Calculator." — remain dry-run, no actual action.
- "What's my dog's name?" — needs personal memory; Decisions must not release an invented direct answer.
- "What's tomorrow's weather?" — current data; Decisions prediction must not fabricate a live result.
- Interrupt speech with a new simple question; no stale Core result and no audio crossing turns.
- Sign off with "Thanks Jarvis, that's all" at least once, and mention those words *as a quotation* while asking a continuing question.

## Analyze logs

Once `repair12_baseline.log` and `repair12_decisions.log` exist in `.runtime`, run:

`python .\scripts\repair12_latency_report.py .runtime\repair12_baseline.log .runtime\repair12_decisions.log`

The report lists the **observed** already-awake direct first-audio latency median/p90, Mini router median, Decisions route agreement/disagreement, and **hypothetical** router time headroom. The difference in first-audio latency is a shadow overhead comparison, **not** the speed increase we could obtain by using Decisions as the router.

## Pass criteria / next step

Both modes run without audio leaks, broken sleep, regressions, or hidden actions; Mini direct and Luna delegation are correct; no unhandled exceptions; budget/error rates are acceptable; 20+ direct comparisons per arm. Don't claim 500–800 ms until it is observed from user speech stop to first audible PCM. Only after evaluating matched headroom and safety do we decide whether to develop an actual Decisions-authorized fast path in Repair13.
