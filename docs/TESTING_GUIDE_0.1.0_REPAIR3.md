# 0.1.0 Repair3 — Testing Guide

Do not commit until automated and live acceptance both pass.

## 1. Focused tests

```powershell
python -m unittest `
  tests.unit.test_0_1_0_repair3_orb_state_transitions `
  tests.unit.test_0_1_0_repair2_desktop_presence `
  tests.unit.test_0_1_0_repair1_desktop_polish `
  tests.integration.test_0_1_0_repair1_desktop_routing `
  tests.unit.test_0_1_0_desktop_contract `
  tests.integration.test_0_1_0_desktop_host -v
```

## 2. Desktop check

```powershell
npm run desktop:check
```

## 3. Full regression

```powershell
python -m unittest discover -s tests -v
```

## 4. Diagnostics

```powershell
python -m core.diagnostics
```

Expected final status: `Status: ok`.

## 5. Live desktop acceptance

```powershell
npm run desktop
```

Say these exact phrases:

1. **“Jarvis, tell me something interesting about space.”**
2. **“Why does that happen?”**
3. **“Explain it more simply.”**
4. While Jarvis is still speaking #3: **“Tell me another interesting fact.”**
5. **“Tell me a short joke.”**

Confirm:

- state changes are gradual rather than hard cuts,
- READY remains calm blue/violet,
- LISTENING shifts toward cyan and subtly focuses/expands,
- THINKING becomes more violet and spins/swurls faster,
- SPEAKING becomes brighter without obvious bouncing,
- WORKING has a distinct faster teal stream,
- the same particles continue through transitions rather than regenerating,
- Realtime response latency and interruption behavior remain unchanged,
- captions still reveal character-by-character.
