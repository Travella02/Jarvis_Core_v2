# 0.1.3 Decisions Shadow - Windows Test Guide

## Scope and privacy
- Accepted 0.1.2 audio architecture is untouched. Decisions is opt-in, *read-only* and billed separately.
- Each eligible transcript is sent to OpenAI /v1/decisions using a Core-owned API key; no audio is sent by the shadow. This is **additional** model processing.
- No predictions authorize tool execution, Luna delegation, or sleep; Mini keeps complete authority.
- Run locally with development conversation tracing; never send logs containing sensitive user speech publicly.

## Install
1. Close Jarvis fully. Extract the patch ZIP into the project root.
2. Run `python .\apply_0_1_3_decisions_shadow_patch.py`.
3. Run `python -m unittest tests.unit.test_0_1_3_decisions_shadow -v`.
4. Run `python -m unittest discover -s tests -v`.
5. Run `python -m core.diagnostics`.
6. Run `npm run desktop:check`.

## Live A/B
First, compare the accepted path using `python .\scripts\realtime_ab.py mini-overlap`. Then close it and run `python .\scripts\realtime_ab.py mini-overlap-decisions-shadow`.

Five standard phrases (say naturally, don't force exact wording):
1. While asleep: **"Hey Jarvis, what planet is known as the Red Planet?"** (wake + correct spoken direct response).
2. While awake: **"Go to sleep, Jarvis."** (silent sleep, local wake resumes).
3. While asleep: **"Jarvis, what's seventeen times six?"** (wake + correct answer).
4. While awake: **"Thanks, Jarvis."** (natural response, remain awake).
5. While awake: **"Thanks Jarvis, that's all."** (sleep silently).

Additional shadow classification coverage:
- **"What's my dog's name?"** (memory, if not in context).
- **"What's tomorrow's weather?"** (current_data; no fabricated live result).
- **"Analyze a complex distributed job queue design."** (ask_luna; dry run).
- **"Open Calculator."** (action; dry run).
- **"That's all."** at an actual sign-off and inside a continuing discussion.

## Acceptance criteria
- Original mini-overlap mode still works and has no Decisions log and no extra Decisions billing.
- Shadow mode logs `[Jarvis Decisions Shadow] phase=result` plus `phase=compare` when transcript + Mini outcome both arrive.
- No Decisions route can affect spoken output or sleep, including inaccurate decisions.
- Spoken naturalness, no popping, turn isolation, wake/sleep and interruption remain unchanged.
- Benchmark end-to-end first-audio with and without the observer; distinguish wake latency from already-awake latency.
- Tests pass before live acceptance; do not remove apply files/backup or commit if any failure occurs.
- A sleep transition can cancel an unfinished observational request. This must not delay or block sleep.

## Next decision
Compare *matched spoken turns*, not standalone Decisions request time alone. Don't switch to Decisions routing until reliability, transcript-availability latency, fallback, confidence calibration and permission authority are validated.
