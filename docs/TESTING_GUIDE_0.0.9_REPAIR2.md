# Jarvis Core v2 0.0.9 Repair2 - Testing Guide

## 1. Apply Repair2

Extract the Repair2 ZIP directly into the existing **0.0.9 Repair1** project root and run:

```powershell
python apply_0_0_9_repair2_patch.py
```

Do not delete patch/apply/backup artifacts or commit until WebRTC live acceptance passes.

## 2. Focused Repair2 + 0.0.9 tests

```powershell
python -m unittest `
  tests.unit.test_0_0_9_repair2_webrtc_contract `
  tests.integration.test_0_0_9_repair2_webrtc_session_creation `
  tests.unit.test_0_0_9_repair1_live_audio_continuity `
  tests.unit.test_0_0_9_voice_frontend_contract `
  tests.unit.test_0_0_9_live_transcript_buffer `
  tests.integration.test_0_0_9_openai_live_transport `
  tests.integration.test_0_0_9_live_client_delegation `
  tests.integration.test_conversation_core -v
```

Expected Repair2 candidate summary: **31 tests, OK**.

These tests prove that WebRTC session creation omits raw PCM format, preserves client delegation and Meridian voice selection, keeps the API key server-side, normalizes WebRTC/DataChannel events through the existing provider-neutral contract, and preserves the existing WebSocket path.

## 3. Full regression

```powershell
python -m unittest discover -s tests -v
```

Expected Repair2 candidate summary: **359 tests, OK** with the existing single skip.

## 4. Configuration doctor

```powershell
python -m apps.gpt_live_lab --doctor
```

Expected key values remain:

```text
model=gpt-live-1
voice=meridian
Health: configured
```

The doctor's PCM line describes the retained WebSocket transport. WebRTC does not pin a PCM format; it negotiates media during connection setup.

## 5. Meridian WebRTC live acceptance

Run:

```powershell
python -m apps.gpt_live_webrtc_lab --turns 5 --voice meridian
```

A localhost browser page should open automatically.

### Exact browser actions

1. Click **Enable audio devices**.
2. Allow microphone permission if the browser asks.
3. In the microphone dropdown, choose **HyperX Cloud Alpha Wireless** (or the HyperX microphone label shown by the browser).
4. In the speaker dropdown, choose **HyperX Cloud Alpha Wireless / Headphones** if available. If the browser cannot select an output device, make the HyperX headset the Windows/browser default output.
5. Click **Start GPT-Live test**.
6. Wait until the status says the GPT-Live WebRTC session is ready, then begin phrase 1.

### Say these exact five phrases

1. **"Jarvis, tell me something interesting about space."**
2. **"Why does that happen?"**
3. **"Explain it more simply."**
4. **While Jarvis is still speaking #3, interrupt naturally with: "Tell me another interesting fact."**
5. **"Tell me a short joke."**

### Pass criteria

- Meridian speech is played by the browser WebRTC media path, not Python `sounddevice`/PortAudio.
- The recurring pops/clicks are gone or materially reduced compared with the WebSocket lab.
- No chipmunk/pitch-shifted playback occurs.
- No new robotic/underwater artifact is introduced.
- Phrase 4 interruption feels natural and the stale answer does not resume afterward.
- All five meaningful turns delegate through Jarvis Core/Luna.
- The terminal reaches `Delegated backend turns completed: 5` and `Status: ok`.

If the browser does not open automatically, run with `--no-browser` and manually open the localhost URL printed in the terminal (default `http://127.0.0.1:8765/`).

## 6. Retained WebSocket diagnostic (optional)

The previous raw-PCM path remains available for comparison:

```powershell
python -m apps.gpt_live_lab --turns 5 --input-device 1 --output-device 4 --voice meridian
```

Do not use this result to reject WebRTC merely because the known local PCM popping remains; its purpose is transport A/B/debugging.

## 7. Local fallback smoke test

After WebRTC acceptance, verify the accepted local provider still behaves normally:

```powershell
python -m apps.voice_lab --turns 5 --tts-provider qwen3-streaming --voice-profile tanner-test --input-device 1
```

Use the same five phrases/actions above.

## 8. Cleanup / commit

Only after acceptance:

1. remove all `apply_0_0_9*` patch scripts, `patch_files/`, `.patch_backups/`, and candidate/repair ZIPs copied into the project root;
2. rerun the full regression;
3. inspect `git status --short --untracked-files=all` and `git diff --check`;
4. verify `.env`, `.venv`, `.runtime`, `runtime/`, caches, models, backups, and patch artifacts are not staged;
5. commit 0.0.9 as one focused milestone.
