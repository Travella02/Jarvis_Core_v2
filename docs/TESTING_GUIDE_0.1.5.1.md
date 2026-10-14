# 0.1.5.1 — First Real Tool Foundation: Testing

**Prerequisite:** Begin at the clean accepted 0.1.4 Git commit (`f6f8a5a` per your last `git log`). Extract patch into the repository root and run `python .\apply_0_1_5_1_patch.py`. No automatic execution should occur during installation.

## 1. Offline focused tests (never open a real browser)

```powershell
python -m unittest tests.unit.test_0_1_5_1_tool_gateway -v
```

Expected: **9 passed**. They test no authorization, wrong turn, negation, unknown sites/tools, browser failures, injection and concurrency.

## 2. Existing automated regression checks

Run each command separately:

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

The suite should be green; never assume an exact total beyond the focused tests as dependencies/environments vary.

## 3. Manual real action (the only NEW live capability in this patch)

First simulate (no browser should open):

```powershell
python .\scripts\tool_gateway_demo.py
```

Then explicitly perform **one** real action:

```powershell
python .\scripts\tool_gateway_demo.py --open-youtube
```

Expected: your default browser is *requested* to open exactly one new YouTube tab. The terminal prints `status=succeeded` only if the OS browser launcher accepted the request. Check the actual tab yourself: that is the independent visual acceptance. If it prints `failed`, capture the error. No UI/voice action is yet expected.

## 4. Existing voice regression (unchanged, important)

```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided
```

Five standard checks to speak:

1. "Hey Jarvis, what planet is called the Red Planet?" → wakes and answers Mars in one utterance.
2. "Go to sleep, Jarvis." → sleeps silently.
3. "Jarvis, what's seventeen times six?" → wakes and says 102.
4. "Thanks, Jarvis." → acknowledges and stays awake.
5. "Thanks Jarvis, that's all." → sleeps quietly.

Also verify ordinary naturalness, no new popping, and direct-response latency consistent with 0.1.4. **A spoken `Jarvis, open YouTube` is still intentionally dry-run in 0.1.5.1.** It becomes an end-to-end voice acceptance criterion in 0.1.5.2.

## 5. Hold / cleanup / commit rules

Do not delete patch files/backups or commit until manual acceptance. After acceptance, remove only the extracted installer, `patch_files`, and its `.patch_backups` created by this patch, check `git status --short`, confirm new source/docs/tests are staged correctly, and commit as the 0.1.5.1 accepted checkpoint. Never use `git clean -fd` blindly.
