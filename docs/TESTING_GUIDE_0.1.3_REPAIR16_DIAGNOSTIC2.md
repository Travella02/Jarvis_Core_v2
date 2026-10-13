# Jarvis Repair16 Diagnostic2 — Windows live instructions

## Install and validate
Close Jarvis. Extract this ZIP **contents** to `Jarvis_Core_v2` project root. Check `Test-Path .\apply_0_1_3_repair16_diagnostic2.py` returns `True`. Run:

```powershell
python .\apply_0_1_3_repair16_diagnostic2.py
```

Then individually:

```powershell
python -m unittest tests.unit.test_0_1_3_repair16_diagnostic2 -v
```

```powershell
python -m unittest discover -s tests -v
```

```powershell
python -m core.diagnostics
```

```powershell
npm run desktop:check
```

```powershell
npm run desktop:build
```

## Live test — baseline first
Start in a **new terminal** with no temporary output cap override:

```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim
```

Wake with `Hey Jarvis`. Ask: `Jarvis, compare three production architectures for a multi-tenant AI assistant, including tenant isolation, authorization, retries and audit logging. Explain trade-offs and recommend one.`

Find `[Jarvis Luna Budget] ... diagnostic_match=... | model=... | output_limit=... | response_status=... | incomplete_reason=... | input_tokens=... | output_tokens=... | reasoning_tokens=...`. Capture nearby `[Jarvis Luna Diagnostic]` and `phase=result` lines. Do **not** send `.env`, API keys, raw provider responses, request bodies, or full unredacted account details. `n/a` means provider omitted the value; `diagnostic_match=false` means exact response-ID telemetry was unavailable.

## Only if `incomplete_reason=max_output_tokens`
Close Jarvis. In the *same PowerShell terminal you will launch Jarvis from*, temporarily set:

```powershell
$env:JARVIS_OPENAI_VOICE_MAX_OUTPUT_TOKENS = '1024'
```

Then launch:

```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim
```

Ask **the same architecture question**. Confirm `output_limit=1024` on the budget line. If Core succeeds, verify Jarvis actually *speaks the analysis* rather than relaying instructions to Luna. Also ask `What's nine times eight?` to ensure normal Mini still answers swiftly. After closing Jarvis, clear the override:

```powershell
Remove-Item Env:JARVIS_OPENAI_VOICE_MAX_OUTPUT_TOKENS -ErrorAction SilentlyContinue
```

If the reason was *not* max output tokens, skip this experiment and send the baseline safe log fields instead. If a request is `completed` but spoken content is still instructions rather than Luna's answer, report that separately: completion and speech delivery are distinct problems.

## Safety/acceptance
Do not speak truncated partial results; no Core actions enabled; no random repeats under failure; no delete/commit until live acceptance. Use the five standard wake/sleep tests and delayed-result cancellation mode from Repair16 after delegation succeeds.
