# Jarvis Core v2 0.0.9 Repair3 — Testing Guide

## 1. Apply Repair3

Extract the Repair3 ZIP directly into the current **0.0.9 Repair2** project root and run:

```powershell
python apply_0_0_9_repair3_patch.py
```

Do not delete patch/apply/backup artifacts or commit until live WebRTC acceptance passes.

## 2. Focused Repair3 + WebRTC tests

```powershell
python -m unittest `
  tests.unit.test_0_0_9_repair3_webrtc_sdp_framing `
  tests.integration.test_0_0_9_repair3_webrtc_creation_diagnostics `
  tests.unit.test_0_0_9_repair2_webrtc_contract `
  tests.integration.test_0_0_9_repair2_webrtc_session_creation `
  tests.unit.test_0_0_9_voice_frontend_contract `
  tests.integration.test_0_0_9_live_client_delegation `
  tests.integration.test_conversation_core -v
```

Expected: all tests pass.

## 3. Full regression

```powershell
python -m unittest discover -s tests -v
```

Expected candidate count after Repair3: **364 tests, OK** with the existing single skip.

## 4. Diagnostics

```powershell
python -m core.diagnostics
```

Expected final line:

```text
Status: ok
```

## 5. Meridian WebRTC live acceptance

Run:

```powershell
python -m apps.gpt_live_webrtc_lab --turns 5 --voice meridian
```

Browser actions:

1. Click **Enable audio devices**.
2. Allow microphone access.
3. Select **HyperX Cloud Alpha Wireless** for microphone.
4. Select the HyperX headphones for speaker output if available.
5. Click **Start GPT-Live test**.
6. Confirm the page prints **ICE gathering complete.** and then **GPT-Live WebRTC session ready**.

Say these exact phrases:

1. **"Jarvis, tell me something interesting about space."**
2. **"Why does that happen?"**
3. **"Explain it more simply."**
4. While Jarvis is still speaking #3, interrupt with **"Tell me another interesting fact."**
5. **"Tell me a short joke."**

Pass criteria:

- WebRTC session creation succeeds.
- Meridian audio is played by browser WebRTC, not Python PCM playback.
- No chipmunk/pitch-shifted output.
- Pops/clicks are gone or materially reduced versus the retained WebSocket lab.
- Phrase 4 interruption does not resume stale speech.
- Five delegated backend turns complete through Jarvis Core/Luna.

If OpenAI still rejects session creation, capture the full status text. Repair3 now exposes the OpenAI error body and request ID, which is the evidence required for the next fix instead of guessing.
