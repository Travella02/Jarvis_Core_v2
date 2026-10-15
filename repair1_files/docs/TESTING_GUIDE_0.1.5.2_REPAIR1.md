# 0.1.5.2 Repair1 Live Acceptance Guide

Close desktop first. After extracting patch ZIP into Jarvis_Core_v2 root, install in this order:

```powershell
python .\apply_0_1_5_2_repair1_patch.py
```
```powershell
python -m unittest tests.unit.test_0_1_5_2_repair1_action_polish -v
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
```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-actions
```

## Five standard voice regression phrases
1. "Hey Jarvis."
2. "What's seventeen times twenty-three?" (391)
3. "What planet is called the Red Planet?" (Mars)
4. "What's the capital of France?" (Paris)
5. "Thanks Jarvis, that's all." (sleep)

Then wake again and test action UX:
- "Jarvis, open YouTube." -> ONE new YouTube tab, no spoken success confirmation, Ready after completion.
- "Jarvis, can you open YouTube for me?" -> ONE new YouTube tab; natural variant authorized, no spoken success.
- "Could you please open YouTube?" -> ONE YouTube tab, no spoken success.
- "Don't open YouTube." -> NO browser launch.
- "Open Google." -> NO browser launch; should show a truthful refusal and return to Ready, NEVER stuck in Working.
- Type "open YouTube" into chat -> ONE YouTube tab, no spoken confirmation.
- "Thanks Jarvis, that's all." -> sleep.

Full unittest discover should not beep. Confirm the default guided mode without `-actions` still does not perform real browser actions.

If anything opens unexpectedly, repeats, hangs in Working, plays a beep, or the voice regresses, STOP. Keep patch files and backups until acceptance and do not commit yet.
