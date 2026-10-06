# 0.1.0 Repair1 Testing Guide

## Focused automated gate

```powershell
python -m unittest `
  tests.unit.test_0_1_0_repair1_desktop_polish `
  tests.integration.test_0_1_0_repair1_desktop_routing `
  tests.unit.test_0_1_0_desktop_contract `
  tests.integration.test_0_1_0_desktop_host -v
```

Then run:

```powershell
npm run desktop:check
python -m unittest discover -s tests -v
python -m core.diagnostics
```

## Live Desktop Alpha acceptance

Launch only Electron; do not separately start Core:

```powershell
npm run desktop
```

Say these exact phrases:

1. `Jarvis, tell me something interesting about space.`
2. `Why does that happen?`
3. `Explain it more simply.`
4. While Jarvis is still speaking #3: `Tell me another interesting fact.`
5. `Tell me a short joke.`

Verify:

- the particle orb animates smoothly and visibly changes behavior across listening/thinking/speaking states;
- captions reveal progressively near spoken pace rather than racing ahead of Cedar;
- interruption #4 does not continue revealing transcript that was never spoken;
- no `StaticFiles`/WebSocket `AssertionError` traceback appears in the terminal;
- terminal prints `[Desktop latency]` lines for spoken turns;
- Realtime Mini + Cedar remains responsive, natural, and pop-free;
- typed input still enters the same Realtime conversation.

Do not commit until live acceptance passes.
