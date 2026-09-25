# 0.0.4-repair12 — Multi-Voice Reference Library

## Scope

Repair12 adds a provider-neutral local voice-reference library for Voice Lab. Personal voice audio is runtime user data and remains outside Git under `.runtime/voice/references/`.

Each named voice gets its own profile directory and manifest. A profile can hold multiple reference clips, has one primary reference, and resolves into the existing Core `VoiceProfile` contract. Qwen, Chatterbox, or future TTS adapters consume the resolved contract; they do not own the library format.

## New Voice Lab workflows

Create/list the private library:

```powershell
python -m apps.voice_lab --voice-library
```

Save a new named voice from any clean local reference clip:

```powershell
python -m apps.voice_lab --save-voice-profile "Tanner Test" `
  --tts-provider qwen3 `
  --voice-ref "C:\path\to\clean_reference.wav" `
  --voice-ref-text "Exact words spoken in the reference clip." `
  --voice-language English
```

Run Qwen with the saved profile instead of passing a file path every time:

```powershell
python -m apps.voice_lab --turns 3 --tts-provider qwen3 --voice-profile tanner-test
```

Saving another clip with the same stable profile ID appends a reference instead of overwriting the existing voice. The newest reference becomes primary unless `--keep-primary-reference` is supplied.

## Qwen model boundary

The current `Qwen3-TTS-12Hz-0.6B-Base` candidate is the cloning checkpoint: it requires a reference voice. Qwen's separate `0.6B-CustomVoice` checkpoint supplies predefined speakers without a user reference. Repair12 does not download or introduce that second model; built-in-vs-cloned launch packaging remains a later product decision.
