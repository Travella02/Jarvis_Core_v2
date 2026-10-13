# Repair16 Diagnostic3 — live Windows procedure

1. Close all Jarvis sessions. Unzip contents into project root; replace patch files (do not run earlier Diagnostic2 apply script again). Verify the installer name:

```powershell
Test-Path .\apply_0_1_3_repair16_diagnostic3.py
```

2. Install, and run each validation separately:

```powershell
python .\apply_0_1_3_repair16_diagnostic3.py
```

```powershell
python -m unittest tests.unit.test_0_1_3_repair16_diagnostic3 -v
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

3. Use the normal trimmed PCM route:

```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim
```

Wake Jarvis, then say:

> Jarvis, compare three architectures for a multi-tenant AI assistant, including authorization, tenant isolation, retries, and audit logs. Recommend one and explain why.

4. Send only **sanitized** terminal lines `[Jarvis Luna Budget]`, `[Jarvis Luna Diagnostic]` and `[Jarvis Luna] phase=result`—no .env, keys, or raw provider responses. In `[Jarvis Luna Budget]`, check `diagnostic_match`, `model`, `output_limit`, `response_status`, `incomplete_reason`, `output_tokens` and `reasoning_tokens`.

If the reason is **max_output_tokens**, run a controlled new-process experiment with an increased output budget (possible extra API charges). Close Jarvis. In the **same terminal** as the next launch:

```powershell
$env:JARVIS_OPENAI_VOICE_MAX_OUTPUT_TOKENS = '1024'
```

```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim
```

Repeat the question; then after closing Jarvis clear the override:

```powershell
Remove-Item Env:JARVIS_OPENAI_VOICE_MAX_OUTPUT_TOKENS -ErrorAction SilentlyContinue
```

Do not claim token exhaustion if reason is not explicitly reported. If provider completed but Jarvis reads instructions to Luna rather than the answer, that's a separate voice-delivery bug. After Core delegation works, run delayed-result cancellation and five standard wake/sleep tests from Repair16. Hold commit/cleanup until accepted.
