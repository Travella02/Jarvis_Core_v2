# Jarvis Core v2 0.1.5.2 Repair2 — Windows Acceptance

Extract the ZIP to Jarvis_Core_v2 root, quit desktop, run each independently:

```powershell
python .\apply_0_1_5_2_repair2_patch.py
```
```powershell
python -m unittest tests.unit.test_0_1_5_2_repair2_action_settlement -v
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
1. "Hey Jarvis." — wakes with short acknowledgment
2. "What's seventeen times twenty-three?" — 391
3. "What planet is called the Red Planet?" — Mars
4. "What's the capital of France?" — Paris
5. "Thanks Jarvis, that's all." — sleeps

## Action tests after waking
1. "Jarvis, open YouTube." — exactly one tab, silent completion, Ready.
2. "Hey, go ahead and open YouTube." — exactly one tab, silent completion, Ready.
3. "Jarvis, can you go ahead and open YouTube for me?" — exactly one tab, silent completion, Ready.
4. "Could you please open YouTube?" — exactly one tab, silent completion, Ready.
5. "Don't open YouTube." — no tab, normal conversation.
6. "Open Google." — no tab; show accurate unsupported-action caption and **Ready within 5 seconds after Core receives it**. Do not speak a success claim.
7. Type `open YouTube` — exactly one tab, silent completion, Ready.
8. "Thanks Jarvis, that's all." — sleeps.

Look for `[Jarvis Action]` (Core outcome) and `[Jarvis Action UI]` (UI acknowledged completion or timeout). If UI stays Working >5 seconds, grab both lines and stop. If missing Core result, do not rerun action automatically. The older guided mode without `-actions` remains a non-executing fallback. Unit tests must not beep.

Do not remove patch files/backups or commit until live acceptance.
