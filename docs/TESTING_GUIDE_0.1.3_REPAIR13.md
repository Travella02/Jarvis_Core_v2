# Jarvis Core v2 0.1.3 Repair13 — Windows test plan

## Install / safety

1. Close any running Jarvis/Electron app and stop the Core terminal.
2. Extract Repair13 ZIP **directly into project root**, preserving `patch_files` and `apply_0_1_3_repair13_patch.py`.
3. `python .\apply_0_1_3_repair13_patch.py` (do not force overwrites if hash mismatch). Existing Repair12 patch files/backups remain untouched.
4. `python -m unittest tests.unit.test_0_1_3_repair13_pcm_onset -v`
5. `python -m unittest discover -s tests -v`
6. `python -m core.diagnostics`
7. `npm run desktop:check`
8. `npm run desktop:build` to confirm the **renderer** compiles on Windows (desktop:check checks only Electron entrypoint).

Do not clean up or Git commit until user approves live behavior. Keep Repair12 rollback artifacts too.

## Matched A/B: only PCM leading-silence trim differs

**Baseline A:** `python .\scripts\realtime_ab.py mini-overlap-luna` (`pcm_trim=off`)

**Experimental B:** `python .\scripts\realtime_ab.py mini-overlap-luna-trim` (`pcm_trim=on`)

No Decisions API in either mode. Both must print `core_luna=on`, `ACTIONS DRY RUN`, model `gpt-realtime-2.1-mini`. Quit completely between arms; same mic, speaker, network and conversational pacing.

### Five standard wake/sleep checks per arm

1. Asleep: **Hey Jarvis, what planet is called the Red Planet?** — wakes and answers Mars.
2. Awake: **Go to sleep, Jarvis.** — sleeps, without extra audio.
3. Asleep: **Jarvis, what's seventeen times six?** — wakes and answers 102.
4. Awake: **Thanks, Jarvis.** — stays awake.
5. Awake: **Thanks Jarvis, that's all.** — verified compound sleep, no voiced dismissal.

### Speed and correctness

- After wake, ask **20+** comparable short direct questions per arm. Use the same order or reverse every second run. Exclude first (wake) turn in per-mode medians.
- Include: "What's seventeen times twenty-three?", "Which planet is called the Red Planet?", "What's the capital of France?", "What's nine times eight?", "Tell me a fact about space." Look for complete, factual answers and consistent speech quality. Do not optimize by shortening outputs or suppressing responses.
- Include a low-volume/soft answer and a longer answer with a natural pause: verify no clipped first syllables or mid-sentence silences.
- Test "Open Calculator" (must stay dry run) and "Explain a complex distributed queue" (Core/Luna delegation); the initial private Mini candidate must never be heard before authorization.
- Interrupt an ongoing long response with another question, ensuring no previous-turn audio leaks or stale answers.
- Check for pops, underflow logs, silent replies, missing words, network disruptions or crashes.

## Capture report

Save full terminal output (without private secrets) as `.runtime\repair13_baseline.log` and `.runtime\repair13_trim.log`. In terminals where Start-Transcript doesn't capture output, copy/paste manually to logs. Then run:

`python .\scripts\repair13_latency_report.py .runtime\repair13_baseline.log .runtime\repair13_trim.log`

Report prints **observed** first-audio median/p90 and new `[Jarvis Latency Detail]` columns:

- `route_ms`: Mini classification relative to speech end.
- `pcm_signal_ms`: earliest audible-amplitude provider sample delivered to AudioWorklet; sampled on renderer callback, not provider generation timestamp.
- `pcm_buffer_ready_ms`: after 45 ms of queued PCM (within worklet).
- `gate_authorized_ms`: after routing + same-turn speech evidence.
- `first_audio_ms`: callback when the worklet emits its first nontrivial audio block (speaker hardware delay not included).
- `pcm_trim_enabled`: true/false to distinguish actual conditions.

**Success:** Experimental B improves observed first-audio median without a regression in correctness, voice integrity, private audio, sleep or Luna. Target is eventually <1000ms median then 500–800 ms. **Do not claim success from offline simulated timing.** If benefits are inconsistent, return to original baseline and use the measurements to choose Repair14. Neither mode changes provider API costs materially; separate audio/model calls are unchanged.
