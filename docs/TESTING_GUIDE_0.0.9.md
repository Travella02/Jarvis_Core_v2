# Jarvis Core v2 0.0.9 — Testing Guide

## 1. Apply the candidate

Extract the patch ZIP directly into the accepted 0.0.8 project root, activate `.venv`, then run:

```powershell
python apply_0_0_9_patch.py
```

0.0.9 adds **no new dependency**. It uses the already-pinned `websockets==15.0.1` and the existing OpenAI/Luna API key.

Do not delete the apply script, `patch_files/`, or `.patch_backups/`, and do not commit until live acceptance is complete.

## 2. Focused automated tests

```powershell
python -m unittest `
  tests.unit.test_0_0_9_voice_frontend_contract `
  tests.unit.test_0_0_9_live_transcript_buffer `
  tests.integration.test_0_0_9_openai_live_transport `
  tests.integration.test_0_0_9_live_client_delegation `
  tests.integration.test_conversation_core -v
```

Expected candidate summary: **19 tests, OK**.

These tests cover the provider-neutral frontend contract, OpenAI Live session schema/event transport over a local fake WebSocket, transcript/delegation correlation, stale-result suppression, existing Conversation Core authority, and cancellation semantics without spending API money.

## 3. Full regression

```powershell
python -m unittest discover -s tests -v
```

Expected candidate summary: **347 tests, OK** with the existing single skip.

## 4. Core diagnostics

```powershell
python -m core.diagnostics
```

Expected shape includes:

```text
Voice: ... frontend=ready, live-bridge=ready ...
Candidates: ... Frontend A/B=local-chain + openai-gpt-live
Status: ok
```

## 5. GPT-Live configuration doctor

```powershell
python -m apps.gpt_live_lab --doctor
```

This makes no network request and captures no microphone audio. It should report:

- version `0.0.9`;
- frontend `openai-gpt-live`;
- model `gpt-live-1` unless overridden;
- built-in voice `meridian` unless overridden;
- `Health: configured` when `OPENAI_API_KEY` is present.

If it reports `not-configured`, verify the existing project `.env` contains the OpenAI API key already used by Luna. Do not paste the key into chat or commit it.

## 6. Live GPT-Live A/B acceptance

Run:

```powershell
python -m apps.gpt_live_lab --turns 5 --input-device 1
```

If device 1 is no longer the intended microphone, run the existing Voice Lab device listing first and substitute the correct input device. The GPT-Live lab uses the default output device unless `--output-device` is supplied.

### Exact five phrases/actions

Say these in order:

1. **“Jarvis, tell me something interesting about space.”**
2. **“Why does that happen?”**
3. **“Explain it more simply.”**
4. **While Jarvis is still speaking the response to #3, interrupt naturally with: “Tell me another interesting fact.”**
5. **“Tell me a short joke.”**

### What must pass

- GPT-Live starts and audio sounds substantially natural enough for meaningful A/B evaluation.
- The five substantive turns are delegated through Jarvis Core/Luna; the lab prints delegated backend completions.
- Follow-up phrases work without repeating the wake name after turn 1.
- Turn 4 behaves as a natural full-duplex interruption/correction and does not later speak stale backend commentary from the superseded request.
- No duplicate Jarvis responses occur.
- The lab ends with `Status: ok` and reports observed Live usage seconds.
- Note any audible artifacts, unnatural timing, or response latency even if the terminal says `ok`.

This lab is an A/B prototype and intentionally listens immediately; it does not yet test the production wake/sleep session lifecycle.

## 7. Local-chain A/B baseline

Run the accepted local path with the **same five phrases/actions**:

```powershell
python -m apps.voice_lab --turns 5 `
  --tts-provider qwen3-streaming `
  --voice-profile tanner-test `
  --input-device 1
```

Use exactly the same phrases from step 6 and interrupt turn 3 with phrase 4. Compare:

- speech-end -> first audible response;
- interruption speed;
- naturalness/prosody;
- audible artifacts;
- conversational continuity;
- whether GPT-Live feels materially more human than the local chain.

Do not optimize or remove the local path inside 0.0.9 based on expectation alone. The user makes the live A/B acceptance decision.

## 8. Acceptance / cleanup workflow

On any failure stay on 0.0.9 and make Repair1/Repair2 as needed. Compare the relevant V1 reference before changing that subsystem.

Only after live acceptance:

1. remove `apply_0_0_9_patch.py`, `patch_files/`, `.patch_backups/`, and candidate patch ZIPs from the project root;
2. rerun the full regression;
3. run `git status --short --untracked-files=all` and `git diff --check`;
4. verify `.env`, `.venv`, `.runtime`, `runtime/`, caches, models, backups, and patch artifacts are not staged;
5. make one focused 0.0.9 commit.
