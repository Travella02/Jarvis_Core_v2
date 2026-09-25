# Testing Guide — 0.0.4-repair12

1. Run all automated tests:

```powershell
python -m unittest discover -s tests -v
python -m apps.voice_benchmark
```

2. Initialize/list the private voice-reference library:

```powershell
python -m apps.voice_lab --voice-library
```

Expected: `.runtime\voice\references` is printed and no Git-tracked file is created there.

3. Record or prepare a clean reference WAV, then save it:

```powershell
python -m apps.voice_lab --save-voice-profile "Qwen Test Voice" `
  --tts-provider qwen3 `
  --voice-ref "C:\path\to\reference.wav" `
  --voice-ref-text "Exact transcript of the reference recording." `
  --voice-language English
```

4. List profiles again and confirm the saved ID/reference:

```powershell
python -m apps.voice_lab --voice-library
```

5. Run Qwen using only the saved profile ID:

```powershell
python -m apps.voice_lab --turns 3 --tts-provider qwen3 --voice-profile qwen-test-voice
```

6. Optional multi-reference check: save a second clip with `--voice-profile-id qwen-test-voice`. Confirm both references remain listed.

Do not clean repair artifacts or commit 0.0.4 until live acceptance is complete.
