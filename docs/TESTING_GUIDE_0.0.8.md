# Jarvis Core v2 0.0.8 — Testing Guide

## 1. Apply the candidate

Extract the patch ZIP into the existing accepted 0.0.7 project root, activate `.venv`, then run:

```powershell
python apply_0_0_8_patch.py
```

0.0.8 adds no new dependency.

## 2. Focused automated tests

```powershell
python -m unittest `
  tests.unit.test_0_0_8_runtime_protocol `
  tests.integration.test_0_0_8_runtime_client_commands `
  tests.integration.test_0_0_7_runtime_api `
  tests.unit.test_0_0_7_runtime_event_stream `
  tests.integration.test_conversation_core -v
```

Expected: **30 tests, OK**.

## 3. Full regression

```powershell
python -m unittest discover -s tests -v
```

Expected candidate summary: **335 tests, OK** (with the existing single skip).

## 4. Real Client Input & Runtime Control Lab

```powershell
python -m apps.runtime_api_lab
```

Expected shape:

```text
Jarvis Core v2 0.0.8 - Client Input & Runtime Control Lab
Conversation preserved: yes
Typed command: accepted through HTTP and correlated on the event stream
Retry safety: duplicate client_request_id executed provider once
Reconnect: cursor=... -> ... | replayed=... events
Cancellation: active client command cancelled through Conversation Core
Exposure: loopback-only; authenticated remote transport remains deferred
Status: ok
```

This uses a real local socket but no microphone, Qwen, Whisper, Luna credential, or public Internet.

## 5. Core diagnostics

```powershell
python -m core.diagnostics
```

Runtime/API diagnostics should remain healthy.

## 6. Accepted Voice Lab regression

0.0.8 must not change the accepted voice behavior. Use the same accepted configuration:

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

Use the standard five phrases and interrupt one answer naturally. This is regression-only; 0.0.8 does not intentionally tune voice latency.

## 7. Manual API behavior worth checking only if needed

The automated/lab coverage already tests the client contract. Do not expose the API to a LAN address. If manually inspecting JSON, confirm:

- ACK trace IDs are server generated;
- retrying an accepted `client_request_id` does not create a second turn;
- stale runtime/conversation IDs are rejected;
- cancel routes through the active client command and does not create a new user turn.

## 8. Acceptance / cleanup workflow

Do not commit immediately after applying. On any failure stay on 0.0.8 and create Repair1/Repair2 as needed.

Only after live acceptance:

1. remove `apply_0_0_8_patch.py`, `patch_files/`, `.patch_backups/`, and candidate patch ZIPs from the project root;
2. rerun the full regression;
3. inspect `git status --short --untracked-files=all` and `git diff --check`;
4. verify `.env`, `.venv`, `.runtime`, `runtime/`, caches, model files, and backups are not staged;
5. make one focused 0.0.8 commit.
