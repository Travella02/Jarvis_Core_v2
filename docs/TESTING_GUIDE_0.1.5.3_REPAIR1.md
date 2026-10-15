# 0.1.5.3 Repair1 — Windows Live Acceptance

Close Jarvis and extract the ZIP to `Jarvis_Core_v2` project root; keep it until test acceptance.

## 1. Apply guarded patch
```powershell
python .\apply_0_1_5_3_repair1_action_feedback.py
```
## 2. Regression tests (no intentionally audible test beeps added)
```powershell
python -m unittest tests.unit.test_0_1_5_3_repair1_action_voice -v
```
```powershell
python -m unittest discover -s tests -q
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
## 3. Live comparison (run each separately; close Jarvis between modes)
Baseline, optional:
```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided
```
Experimental action mode:
```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-semantic
```
## 4. Five standard phrases, measured for first audio
1. “Hey Jarvis.” — short wake greeting.
2. “What is seventeen times twenty-three?” — answer 391.
3. “What planet is called the Red Planet?” — answer Mars.
4. “What is the capital of France?” — answer Paris.
5. “Thanks Jarvis, that's all.” — Jarvis sleeps.

## 5. Action-result checks (wake Jarvis again)
1. “Open YouTube.” — EXACTLY one new YouTube tab, no spoken success, prompt Working→Ready; log `core_tool_result` / `desktop_action_feedback status=completed` (NOT `result_timeout`).
2. “Thanks for explaining that, could you please open YouTube for me?” — one tab, silent, prompt Ready.
3. “Can you open Google?” — NO tab; brief audible explanation that the destination/capability isn't available; prompt Working→Speaking→Ready; log `status=failed` (NOT unknown timeout).
4. “Open YouTube and send an email.” — NO tab; brief audible rejection if a tool is attempted, or Mini naturally explains unsupported operation. Do not execute.
5. “Could you search YouTube for videos about how black holes form?” — one YouTube results tab. NOTE: actual result/page load not verified by Core.
6. “Don't open YouTube.” — no tab, no action execution.
7. Ask a new question during a tool result; old turn's result must never execute or speak after the new turn.

**Observe actual audible output**, not just a log that synthesis began. The repair has no new native sound cue/beep. Compare common-question latency against the pre-repair checkpoint (at least 10 matched turns per arm). If it regresses materially, do not accept.

Do NOT clean/commit until reporting results. On install guard mismatch, show `git status --short` and do not force overwrite.
