# Jarvis Core v2 — 0.1.5.2 Live Test Guide

## Before tests
- Exit all Jarvis/Electron processes, extract ZIP into the repo root and run installer.
- **Do not delete patch/backups or commit until live acceptance.**
- Run these commands separately from the root (active `.venv`):

```powershell
python .\apply_0_1_5_2_patch.py
```
```powershell
python -m unittest tests.unit.test_0_1_5_2_natural_actions -v
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

## Live A/B action arm (no beeps)
```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-actions
```
Test exactly in this order; speak plainly with a short pause between turns. Observe the actual default browser and the Core logs.

1. While asleep, say **'Hey Jarvis'**. He should acknowledge you naturally.
2. Say **'Jarvis, open YouTube.'** He should open **one** YouTube tab. Logs should show `[Jarvis Action] ... status=completed ... authority=core`. He should not claim YouTube actually loaded, merely that a browser launch was requested.
3. Say **'What's seventeen times twenty-three?'** Expect **391** without opening any tab.
4. Say **'What planet is called the Red Planet?'** Expect **Mars**; no tool execution.
5. Say **'What's the capital of France?'** Expect **Paris**; no tool execution.
6. Say **'Don't open YouTube.'** Expect NO browser launch. The exact expression should be rejected if Mini selects test_action.
7. Say **'Open Google.'** Expect NO browser launch (not approved yet).
8. Say **"Thanks Jarvis, that's all."** Expect verified sleep, without an action or spurious opening.

Typed test (optional but recommended): wake Jarvis and type **'open YouTube'** in the chat input. It should open one tab, and only one.

## Baseline comparison
Completely exit the app, then run:
```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided
```
This mode must **NOT** open YouTube even if you say "Open YouTube" (existing action dry run). It must continue to handle greeting, arithmetic, Mars, France, and sleep normally.

## Safety and acceptance
- Do not accept if a browser opens on the negated command, another site, or a repeated/stale tool response.
- Do not accept if beep cues play during these A/B tests.
- A failed or missing action should never be reported as successful.
- Record real response audio quality and whether mic breathing/taps falsely interrupt speech; the known VAD issue is out of scope here.
- Normal `unit.test_0_1_3...cue` tests mock native sound; the new A/B flag independently suppresses cues even during opt-in cancellation experiments.
