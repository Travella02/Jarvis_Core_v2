# 0.0.4-repair16 Live Testing

1. Apply the repair from the project root.
2. Run the full automated test suite and Voice benchmark.
3. Confirm the Qwen provider is healthy.
4. Run the clone diagnostic against the saved test voice:

```powershell
python -m apps.voice_lab --qwen-clone-diagnostic `
  --voice-profile tanner-test `
  --tts-diagnostic-text "Jarvis voice diagnostic. This sentence should sound clear and natural."
```

The diagnostic prints:
- reference file format, sample rate, channels and duration;
- peak/RMS/clipping/near-silence metrics;
- whether a saved reference transcript exists;
- direct full-reference clone duration and WAV path;
- direct x-vector-only clone duration and WAV path.

Listen to any generated WAVs.

## Interpretation
- Both direct WAVs sound correct: Qwen/runtime/reference are viable; repair the normal cached Jarvis adapter path next.
- x-vector works but full-reference clone fails: inspect the exact transcript and ICL/reference-code path.
- Both produce tiny/noise output while reference metrics are clean: runtime/model combination is the leading suspect.
- Reference metrics warn about very short, quiet, clipped or mostly silent audio: replace the reference clip before judging Qwen.
