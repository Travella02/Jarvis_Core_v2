# 0.0.4-repair7 Live Testing Guide

## 1. Automated regression

```powershell
python -m unittest discover -s tests -v
python -m apps.voice_benchmark
```

Expected: all tests pass and Voice benchmark is 4/4.

## 2. List devices with host API/native rate

```powershell
python -m apps.voice_lab --devices
```

Find the desired physical headset microphone. Duplicate names from MME/DirectSound/WASAPI/WDM-KS are expected; repair7 now shows the host API so each endpoint is distinguishable.

## 3. Verify the microphone without spending Luna/TTS work

Example:

```powershell
python -m apps.voice_lab --mic-test --input-device 17 --mic-test-seconds 5
```

The command must print the exact selected endpoint and a moving level meter while speaking. A 44.1/48 kHz native device should be shown as resampled to Jarvis 16 kHz rather than failing with `Invalid sample rate`.

Try another HyperX endpoint ID if the meter stays flat. Once the correct physical mic is found, persist it:

```powershell
python -m apps.voice_lab --save-devices --input-device 17
```

An explicit `--input-device` on a later run still overrides the saved value.

## 4. Live one-turn latency test

```powershell
python -m apps.voice_lab
```

Before `Listening...`, Voice Lab should print selected input/output and preload local providers. The preload can take noticeable time on a fresh process; it is intentionally outside the conversational latency measurement.

After speaking, capture the stage timing summary:
- endpoint -> STT final
- STT final -> Luna first text
- Luna first text -> TTS first audio
- speech end -> first audible audio

Run at least three fresh turns after the correct microphone is selected before deciding whether Whisper Q5 / Luna / Chatterbox Turbo meets the product latency bar.

## Acceptance

Do not commit 0.0.4 until:
- the intended physical microphone is verified by meter and actual transcription;
- explicit 44.1/48 kHz headset endpoints no longer fail with invalid sample rate;
- both local providers remain healthy;
- post-preload conversational latency is measured and reviewed;
- no provider/model implementation leaks into Conversation Core.
