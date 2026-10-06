# 0.1.0 Desktop App Alpha — Testing Guide

Do not commit until automated and live acceptance both pass.

## 1. Python focused tests

```powershell
python -m unittest `
  tests.unit.test_0_1_0_desktop_contract `
  tests.integration.test_0_1_0_desktop_host `
  tests.unit.test_0_0_9_repair6_realtime_default `
  tests.integration.test_0_0_9_repair4_realtime_core_delegation -v
```

## 2. Electron syntax/security check

```powershell
npm run desktop:check
```

## 3. Full Python regression

```powershell
python -m unittest discover -s tests -v
```

## 4. Core diagnostics

```powershell
python -m core.diagnostics
```

Expected final status: `Status: ok`.

## 5. First-time JS install

Run once on a machine without the desktop dependencies:

```powershell
npm install
```

Do not commit `node_modules/` or `apps/desktop/dist/`.

## 6. Build and launch

```powershell
npm run desktop
```

Expected:

- one native Jarvis window opens (no browser tab),
- the screen is intentionally minimal: JARVIS label, centered avatar, speech transcript, and typed input,
- no second Python Core is manually started,
- microphone permission is scoped to the local Jarvis origin,
- Cedar audio plays through WebRTC without the old PCM popping.

## 7. Exact live voice test

Say these exact phrases:

1. **“Jarvis, tell me something interesting about space.”**
2. **“Why does that happen?”**
3. **“Explain it more simply.”**
4. While Jarvis is still speaking #3: **“Tell me another interesting fact.”**
5. **“Tell me a short joke.”**

Confirm:

- the avatar changes into listening/thinking/speaking states,
- Jarvis's words appear progressively beneath the avatar while he speaks,
- Cedar remains natural and pop-free,
- #4 interrupts naturally.

## 8. Exact typed-input test

Click the input and type:

**`Give me one surprising fact about the ocean.`**

Press Enter.

Confirm:

- the typed message enters the same active Realtime conversation,
- Jarvis responds aloud through Cedar,
- his response types out beneath the avatar while he speaks,
- no separate text-only conversation or Luna-only UI path is created.

Then type:

**`Now explain why that's surprising in one sentence.`**

Confirm Jarvis keeps the context from the previous typed request.

## 9. Shutdown test

Close the Jarvis window normally.

Confirm:

- Electron exits,
- the supervised Python desktop host exits,
- the WebRTC session closes,
- port `8765` is no longer owned by the app.

## 10. Cleanup before commit

Delete patch/apply artifacts only after live acceptance, rerun the full regression, inspect Git, then commit one focused 0.1.0 change.
