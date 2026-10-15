# 0.1.5.3 Semantic Actions — Live Windows Testing

Close Jarvis between each launcher. Keep patch and backups until acceptance. Do NOT commit. Use each command in its own PowerShell prompt.

```powershell
python -m unittest tests.unit.test_0_1_5_3_semantic_actions -v
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

## Baseline: accepted guided voice (NO action experiment)
```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided
```

## New semantic actions experimental arm
```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-semantic
```

**Standard five spoken regression phrases:**

1. "Hey Jarvis."
2. "What is seventeen times twenty-three?" — 391.
3. "What planet is called the Red Planet?" — Mars.
4. "What's the capital of France?" — Paris.
5. "Thanks Jarvis, that's all." — sleeps; wakes again before actions.

**Actions:** Each action should be a fresh, awake turn. Visible success means one tab opens and no spoken completion; *an attempted open is not a verified loaded page*.

1. "Open YouTube." — YouTube homepage opens once.
2. "Thank you for explaining that. Could you please go ahead and open YouTube for me?" — YouTube opens once.
3. "Jarvis, would you mind pulling up YouTube?" — YouTube opens once.
4. "Could you search YouTube for a video about how black holes form?" — YouTube SEARCH RESULTS for black holes (inspect query).
5. "That was really interesting. Can you open YouTube and find me a video about that?" — experimental conversational context challenge; inspect search phrase and report if not grounded. No fabricated success.
6. "Don't open YouTube." — nothing opens.
7. "If you have time later, open YouTube." — nothing opens.
8. "Open Google." — denied and Ready, no browser tab.
9. "Open YouTube and send an email." — denied, no browser tab.
10. "Open YouTube" twice in one turn/click test — one action maximum.
11. Test a genuine new spoken command during a long model answer; old results must not execute.

**Latency A/B:** Speak 20 matched conversational prompts to guided and guided-semantic in alternating sessions. Record `speech_end->first_audio` for simple chat separately from `decision_ms`; compare medians and p95. No production approval if basic conversation becomes materially slower. Do not compare one unrepresentative slow turn.

**Known limitations:** Only one approved destination; YouTube search queries are proposed by Mini and may not reliably resolve "that" without richer conversation context. Complex multi-action workflows, arbitrary URLs, email, tasks and all background browser search are OUT OF SCOPE.
