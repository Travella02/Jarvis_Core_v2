# Testing Guide — Jarvis Core v2 0.0.6 Runtime State & Event Foundation

## Install

Extract the patch ZIP into the existing Jarvis Core v2 project root, activate `.venv`, then run:

```powershell
python apply_0_0_6_patch.py
```

The installer verifies the expected accepted 0.0.5 Repair5f source before changing files and backs up replaced files.

## Focused automated tests

```powershell
python -m unittest `
  tests.unit.test_event_bus `
  tests.unit.test_0_0_6_runtime_settings `
  tests.unit.test_0_0_6_provider_router `
  tests.unit.test_0_0_6_runtime_health `
  tests.integration.test_0_0_6_runtime_foundation `
  tests.unit.test_0_0_6_voice_lab_runtime_wiring -v
```

Expected: all focused tests pass.

## Full regression

```powershell
python -m unittest discover -s tests -v
```

Expected: all tests pass.

## Runtime diagnostic

This makes no live OpenAI request and does not use microphone/TTS:

```powershell
python -m apps.runtime_lab
```

Expected shape:

```text
Jarvis Core v2 0.0.6 - Runtime Lab
Lifecycle: running | Health: healthy
Conversation activity: listening
Turn: completed | Runtime ready.
Reconnect: cursor=... -> ... | events=... | gap=no
Trace events: ...
Status: ok
```

Then run:

```powershell
python -m core.diagnostics
```

Expected: Runtime host/settings/router/replay all report ready; network/audio probes remain `not-run`.

## Live Voice Lab regression

Use the accepted 0.0.5 voice command unchanged:

```powershell
python -m apps.voice_lab --turns 5 `
  --tts-provider qwen3-streaming `
  --voice-profile tanner-test `
  --input-device 1 `
  --qwen-fixed-seed 12345 `
  --tts-response-mode whole `
  --stt-endpoint-final-only `
  --luna-model gpt-6-luna `
  --luna-service-tier default
```

### Five standard voice prompts

1. `Jarvis, tell me something interesting about space.`
2. `Why does that happen?`
3. `Explain it more simply.`
4. `Tell me another interesting fact.`
5. `Tell me a short joke.`

Success means wake/sleep, continuous conversation, confidence validation, whole-response Qwen voice, Luna continuation, and interruption behavior remain unchanged from accepted 0.0.5.

## Runtime acceptance checks

1. Run `python -m apps.runtime_lab` twice. Both runs should end `Status: ok`; no stale runtime or fixed-port conflict exists because 0.0.6 has no network listener/process supervisor yet.
2. Run `python -m apps.runtime_lab --json` and confirm the snapshot contains no API keys or secret values.
3. Run Voice Lab and confirm normal wake/conversation/sleep still works.
4. Interrupt Jarvis during an active response and confirm Conversation Core still maintains the correct context.
5. Quit Voice Lab normally and confirm no pending-task or coroutine-reuse shutdown error is printed.

## Known limitations

- Event replay is in-process memory only. A process restart starts a new runtime/event cursor.
- The actual local network API/client transport is intentionally deferred; 0.0.6 establishes the reconnectable snapshot/event contract first.
- Provider routing is explicit only; no automatic model escalation/fallback is enabled.

## After live acceptance

Do not commit the extracted installer/payload or temporary backup directories. After the live test passes and 0.0.6 is accepted, remove the patch delivery artifacts from the project root before committing:

```powershell
Remove-Item .\apply_0_0_6_patch.py -Force -ErrorAction SilentlyContinue
Remove-Item .\0_0_6_payload -Recurse -Force -ErrorAction SilentlyContinue
```

Keep `.patch_backups` only until the accepted tree is committed and you are satisfied the Git checkpoint is a sufficient rollback point; then remove the specific 0.0.6 backup created by the installer if desired. Never remove user runtime data, `.env`, voice references, OAuth data, or Git history as part of patch cleanup.
