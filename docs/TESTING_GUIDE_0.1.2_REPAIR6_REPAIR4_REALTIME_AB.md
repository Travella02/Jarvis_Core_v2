# 0.1.2 Repair6-Repair4 — Mini vs Full Realtime A/B

## Scope

Model comparison and instrumentation **only**. The existing safe text-only
routing gate still runs. This compares model quality, routing choices, latency,
and billable Realtime tokens on an otherwise consistent pipeline; it does **not**
yet test a gate-free tool-first agent or speculative audio. Luna/Core reasoning
remains the same backend model for both arms.

## Safety / configuration

- Stop the Electron/Jarvis process fully before each model switch.
- Launch commands use process-only env overrides and **never edit `.env`**.
- `JARVIS_PARALLEL_SHADOW_PROBE=0` ensures the unused parallel experiment cannot bias cost/latency.
- Development conversation tracing prints transcripts to the terminal. Do not
  share logs containing private requests, contacts, credentials or file paths.
- No raw chat or API keys are saved into a report file by this patch.
- Costs are estimates from `response.done.usage` using OpenAI standard prices
  published 2026-10-09: https://developers.openai.com/api/docs/pricing .
  Includes Realtime router *and* final audio, plus prompt context tokens;
  excludes OpenAI Core/Luna tokens, STT transcription costs, tool charges and
  network fees. `unpriced_responses > 0` means totals are incomplete.

## Run Mini

```powershell
python .\scripts\realtime_ab.py mini
```

## Run Full

```powershell
python .\scripts\realtime_ab.py full
```

Same voice, reasoning effort, Jarvis version and test order. Restart between
runs; don't ask both sessions at once. Do 2–3 warm-up direct turns per model,
then repeat the comparison prompts 3x each. User review should score:
- audible time to first audio (median and tail)
- correctness, naturalness, absence of false pre-tool claims and filler
- tool-selection precision (direct/long_task/reasoning etc.)
- answer completeness and turn interruption
- input/output token totals and estimated Realtime cost
- availability/actual use of Luna backend (`[Jarvis A/B Core]`)

## Suggested comparable voice prompts (say exactly)

1. "Jarvis, what planet is known as the Red Planet?" (simple/direct)
2. "What is seventeen times six?" (direct)
3. "Explain why idempotency matters when a runtime reconnects." (model chooses direct vs reasoning)
4. "Compare optimistic and pessimistic concurrency for a multi-user app and tell me the main tradeoffs." (hard reasoning; inspect model-selected route)
5. "Jarvis, start a background task that builds a project while I'm gone." (long_task, must say unavailable)
6. "Thanks Jarvis." (must stay awake)
7. "Thanks Jarvis, that's all." (must sleep without speaking)

For explicit backend-model verification, wake Jarvis and also say:
"Jarvis, use your Core to analyze the tradeoffs between event sourcing and a relational database for a small application." 
Look for `[Jarvis A/B Core] ... backend_model=gpt-6-luna` (or your configured strong backend).

## Terminal records

- `[Jarvis A/B Start]`: configured model and shadow-test setting
- `[USER SPEECH]`: accepted user transcript, source and realtime model
- `[Jarvis Route]`: whether Realtime handles direct or Core owns the request
- `[Jarvis A/B Tool]`: every completed function-call argument event
- `[Jarvis A/B Core]`: capability route and actual provider model selected
- `[JARVIS REPLY]`: final user-facing reply, source and realtime model
- `[Jarvis A/B Usage]`: provider token usage and estimated Realtime USD per response
- `[Jarvis A/B Turn]`: length, response latency and aggregate Realtime USD for this turn
- `[Jarvis A/B Session]`: aggregate costs when the control session closes

**Do not mistake `source=core` for the Realtime model itself.** Core is a
separate model/provider. Costs from Core requests are not included in the
Realtime estimate. The Realtime voice still voices Core results.

## Acceptance

Accept only after both models have safely passed identical live tests with
no new duplicate audio, filler before tool results, false action claims,
caption truncation or broken wake/sleep/interruptions. Keep 0.1.2 under repair
until explicit live acceptance; do not commit before cleanup and validation.
