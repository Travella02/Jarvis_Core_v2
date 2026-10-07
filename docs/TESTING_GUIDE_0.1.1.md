# 0.1.1 Wake/Sleep Presence Control — Testing Guide

Do not commit until automated and live acceptance both pass.

## 1. Focused tests

```powershell
python -m unittest `
  tests.unit.test_0_1_1_local_wake_listener `
  tests.unit.test_0_1_1_realtime_sleep_lifecycle `
  tests.unit.test_0_1_1_desktop_wake_sleep_contract `
  tests.integration.test_0_1_1_desktop_presence_lifecycle `
  tests.unit.test_0_0_5_wake_sleep_control `
  tests.unit.test_0_1_0_repair4_playback_responsive -v
```

Expected: **30 tests, OK**.

## 2. Desktop static check

```powershell
npm run desktop:check
```

## 3. Full regression

```powershell
python -m unittest discover -s tests -v
```

Expected: **447 tests, OK**, with the same single existing skip.

## 4. Diagnostics

```powershell
python -m core.diagnostics
```

Expected final line: `Status: ok`. Desktop diagnostics should include `presence=local-wake + realtime-awake + local-sleep`.

## 5. Launch

```powershell
npm run desktop
```

The app should open in **SLEEPING** state. Allow microphone access if prompted. The first local wake preparation may take longer than later sleep/wake cycles because local Whisper can be warming.

## 6. Local sleeping privacy/cost gate

While Jarvis is sleeping, in a second PowerShell window run:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/desktop/health
```

Confirm:

- `presence` is `sleeping`,
- `realtime_active` is `False`,
- the orb remains dormant rather than listening through Realtime.

Say this unrelated phrase while sleeping:

**“This sentence should not wake the assistant.”**

Confirm Jarvis stays asleep and gives no cloud response.

## 7. Embedded wake + opening command

Say exactly:

**“Jarvis, tell me something interesting about space.”**

Confirm:

- Jarvis wakes,
- you do **not** repeat the request,
- the orb transitions smoothly from sleeping -> waking -> thinking/speaking,
- Cedar answers the preserved request.

Then, without saying Jarvis again, say:

**“Why does that happen?”**

Confirm normal continuous conversation works.

## 8. Explicit sleep

Say exactly:

**“That’s all, Jarvis.”**

Confirm Jarvis returns to **SLEEPING** and the Realtime session closes. Re-run the health request and confirm `realtime_active` is `False`.

## 9. Wake-only phrase

Say exactly:

**“Jarvis.”**

Confirm Jarvis wakes to READY without inventing a request. Then say:

**“Tell me a short joke.”**

Confirm he answers without requiring the wake word again.

## 10. Typed wake

Put Jarvis back to sleep with:

**“Go to sleep, Jarvis.”**

Then type exactly:

**`Give me one surprising fact about the ocean.`**

Confirm typed input wakes the same Realtime conversation path and Cedar answers aloud.

## 11. Auto-sleep

After Jarvis finishes a response, do not speak or type for at least **65 seconds**.

Confirm:

- Jarvis smoothly returns to SLEEPING,
- `realtime_active` becomes `False`,
- saying **“Jarvis, are you there?”** wakes him and answers that same utterance.

## 12. Shutdown

Close the app normally. Confirm Electron, the supervised Core host, local wake listener, microphone tracks, and any active Realtime call all terminate.
