# Jarvis Core v2 0.0.7 — Testing Guide

## 1. Apply the candidate

Extract the patch ZIP into the existing Jarvis Core v2 project root, activate `.venv`, then run:

```powershell
python apply_0_0_7_patch.py
```

## 2. Install the new local API dependencies

```powershell
python -m pip install -r requirements.txt
```

0.0.7 directly pins FastAPI, Uvicorn, HTTPX, and WebSockets so the runtime does not depend on accidental/transitive development packages.

## 3. Focused automated tests

```powershell
python -m unittest `
  tests.unit.test_0_0_7_runtime_protocol `
  tests.unit.test_0_0_7_runtime_settings `
  tests.unit.test_0_0_7_runtime_event_stream `
  tests.integration.test_0_0_7_runtime_api `
  tests.unit.test_event_bus `
  tests.integration.test_0_0_6_runtime_foundation -v
```

Expected: **30 tests, OK**.

## 4. Full regression

```powershell
python -m unittest discover -s tests -v
```

Expected candidate summary: **320 tests, OK**.

## 5. Real Runtime API reconnect lab

```powershell
python -m apps.runtime_api_lab
```

Expected shape:

```text
Jarvis Core v2 0.0.7 - Runtime API Lab
Conversation preserved: yes
Reconnect: cursor=... -> ... | replayed=... events
Client contract: Windows / macOS / Linux / iOS / Android
Exposure: loopback-only in 0.0.7; authenticated remote transport is deferred
Status: ok
```

This uses a real local TCP socket, FastAPI/Uvicorn, HTTP, and WebSocket. It does not use your microphone, Qwen, Whisper, Luna, or the public Internet.

## 6. Core diagnostics

```powershell
python -m core.diagnostics
```

Expected runtime line includes:

```text
api=http-websocket-ready, protocol=jarvis-runtime-v1
```

## 7. Accepted Voice Lab regression

0.0.7 should not change the accepted voice path. Run:

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

Use the standard five phrases:

1. `Jarvis, tell me something interesting about space.`
2. `Why does that happen?`
3. `Explain it more simply.`
4. `Tell me another interesting fact.`
5. `Tell me a short joke.`

Interrupt one answer naturally. Success means the existing 0.0.6/0.0.5 voice behavior remains unchanged.

## 8. What not to test yet

Do **not** change `JARVIS_RUNTIME_API_HOST` to `0.0.0.0` or a LAN IP. 0.0.7 intentionally rejects unauthenticated remote exposure. Mobile/macOS/Windows portability in this milestone is a protocol contract, not an insecure network-sharing feature.

## Common failure symptoms

- `ModuleNotFoundError: fastapi/uvicorn/websockets/httpx`: rerun `python -m pip install -r requirements.txt` in the project `.venv`.
- `runtime-identity-required`: the client persisted a cursor without the `runtime_id`; reset from the supplied snapshot.
- `runtime-changed`: Core restarted; discard client-derived state and accept the new snapshot/runtime ID.
- `history-gap` or `replay-limit`: bounded replay cannot safely reconstruct every missed event; accept the snapshot as current truth.
- Port conflict: 0.0.7 diagnostic uses an ephemeral port. Future process supervision must preserve one Core owner and preflight any fixed production port.

## Logs / privacy

The Runtime API snapshot contains non-secret orchestration settings only. Do not paste `.env`, API keys, credentials, access tokens, raw voice reference files, or private future memory stores into bug reports.
