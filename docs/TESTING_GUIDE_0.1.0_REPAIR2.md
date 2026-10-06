# 0.1.0 Repair2 — Testing Guide

Do not commit until automated and live acceptance both pass.

## 1. Focused tests

```powershell
python -m unittest `
  tests.unit.test_0_1_0_repair2_desktop_presence `
  tests.unit.test_0_1_0_repair1_desktop_polish `
  tests.integration.test_0_1_0_repair1_desktop_routing `
  tests.unit.test_0_1_0_desktop_contract `
  tests.integration.test_0_1_0_desktop_host -v
```

Expected: 30 tests, OK.

## 2. Desktop source check

```powershell
npm run desktop:check
```

## 3. Full regression

```powershell
python -m unittest discover -s tests -v
```

Expected: 415 tests, with the same single existing skip.

## 4. Diagnostics

```powershell
python -m core.diagnostics
```

Expected final status: `Status: ok`.

## 5. Live desktop acceptance

```powershell
npm run desktop
```

Say exactly:

1. **“Jarvis, tell me something interesting about space.”**
2. **“Why does that happen?”**
3. **“Explain it more simply.”**
4. While Jarvis is still speaking #3: **“Tell me another interesting fact.”**
5. **“Tell me a short joke.”**

Confirm:

- Jarvis is visibly larger.
- The particles read as a dense flowing sphere/dust intelligence rather than scattered points inside a ring.
- Captions appear letter by letter rather than one word at a time.
- The first visible letters begin around Cedar playout rather than racing ahead of speech.
- Sentence spacing and punctuation look correct; no `word!Next` joins.
- Realtime response latency remains in the same fast range as Repair1.
- Barge-in on #4 still works.
- No StaticFiles/WebSocket traceback returns.

Do not clean patch artifacts or commit until live acceptance passes.
