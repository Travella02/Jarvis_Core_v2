# Testing Guide — 0.0.4-repair8

## Automated regression

```powershell
python -m unittest discover -s tests -v
python -m apps.voice_benchmark
python -m core.diagnostics
```

No dependency or local-model reinstall is required. Existing Whisper/Chatterbox runtime assets under `.runtime/` remain valid.

## Provider readiness

```powershell
python -m apps.voice_lab --provider-health
```

Expected:

```text
STT: ready - local whisper.cpp server ready
TTS: ready - Chatterbox Turbo ready on cuda
```

## Live latency acceptance

Use the persisted working microphone/output from repair7:

```powershell
python -m apps.voice_lab
```

Speak a normal short question such as:

> Jarvis, tell me something interesting about space.

Confirm transcription/voice quality, then capture the complete `Latency marks` and `Turn timing summary`.

Repair8 should print separate timing for:

- endpoint -> STT final
- STT final -> Luna first text
- Luna first text -> first speech chunk
- first speech chunk -> TTS request
- TTS request -> first waveform
- first waveform -> first audible audio
- speech end -> first audible audio

The goal of this repair is to determine the real remaining bottleneck, not to fake a pass. If TTS request -> first waveform is still multiple seconds, Chatterbox itself needs optimization/replacement testing. If STT final -> Luna first text remains high even with `none` reasoning, investigate cloud/provider latency next.

## Spoken-text check
Ask for an answer likely to contain numbers or emphasis. The terminal may display markdown/provider formatting in `Jarvis:` text, but the audible speech should not speak markdown tokens such as `asterisk`, headings, or link syntax.

Do not clean repair artifacts or commit until live acceptance is explicitly complete.
