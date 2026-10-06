# Jarvis Core v2 0.0.9 Repair1 — Testing Guide

## 1. Apply Repair1

Extract the Repair1 ZIP directly into the existing 0.0.9 project root and run:

```powershell
python apply_0_0_9_repair1_patch.py
```

Do not commit or delete patch/apply/backup artifacts until live acceptance passes.

## 2. Focused Repair1 + 0.0.9 tests

```powershell
python -m unittest `
  tests.unit.test_0_0_9_repair1_live_audio_continuity `
  tests.unit.test_0_0_9_voice_frontend_contract `
  tests.unit.test_0_0_9_live_transcript_buffer `
  tests.integration.test_0_0_9_openai_live_transport `
  tests.integration.test_0_0_9_live_client_delegation `
  tests.integration.test_conversation_core -v
```

Expected Repair1 candidate summary: **23 tests, OK**.

The continuity tests specifically prove packet-boundary-independent resampling, 24 kHz default PCM, fixed-frame jitter buffering, and fade-to-zero interruption.

## 3. Full regression

```powershell
python -m unittest discover -s tests -v
```

Expected Repair1 candidate summary: **351 tests, OK** with the existing single skip.

## 4. Configuration doctor

```powershell
python -m apps.gpt_live_lab --doctor
```

Expected audio line now reports:

```text
Voice: meridian | audio=24000 Hz PCM16 mono
```

If your local `.env` explicitly pins `JARVIS_GPT_LIVE_AUDIO_RATE_HZ=16000`, change that local-only value to `24000` for the Repair1 acceptance run. Do not commit `.env`.

## 5. Meridian live audio acceptance

Run:

```powershell
python -m apps.gpt_live_lab --turns 5 --input-device 1 --voice meridian
```

Say these exact phrases/actions:

1. **“Jarvis, tell me something interesting about space.”**
2. **“Why does that happen?”**
3. **“Explain it more simply.”**
4. **While Jarvis is still speaking #3, interrupt naturally with: “Tell me another interesting fact.”**
5. **“Tell me a short joke.”**

### Pass criteria

- Meridian still sounds at least as natural as the pre-repair run.
- The recurring popping/clicking is gone or materially reduced.
- No new robotic/underwater artifact is introduced.
- Turn 4 interruption still feels prompt and does not leave a hard click at the local cutoff.
- No stale prior answer speaks after the correction.
- Five delegated backend turns complete and the lab ends `Status: ok`.
- Startup should show `Live=24000 Hz` unless intentionally overridden.

The lab adds a small ~40 ms playback cushion by design. Judge the total conversational feel as well as the artifact reduction.

## 6. Local fallback smoke test

Repair1 modifies the provider-neutral SoundDevice output resampling path, so run one accepted local voice smoke test after the Live acceptance:

```powershell
python -m apps.voice_lab --turns 5 --tts-provider qwen3-streaming --voice-profile tanner-test --input-device 1
```

Use the same five phrases/actions above. The local path should remain functionally unchanged.

## 7. Cleanup / commit

Only after acceptance:

1. remove all `apply_0_0_9*` patch scripts, `patch_files/`, `.patch_backups/`, and candidate/repair ZIPs copied into the project root;
2. rerun the full regression;
3. inspect `git status --short --untracked-files=all` and `git diff --check`;
4. verify `.env`, `.venv`, `.runtime`, `runtime/`, caches, models, backups, and patch artifacts are not staged;
5. commit 0.0.9 as one focused milestone.
