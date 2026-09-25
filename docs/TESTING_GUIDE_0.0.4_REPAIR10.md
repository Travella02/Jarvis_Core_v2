# 0.0.4-repair10 Live Testing — Audio Input Validation & False-Speech Rejection

Do not clean or commit 0.0.4 until these live checks pass.

## 1. Automated regression

```powershell
python -m unittest discover -s tests -v
python -m apps.voice_benchmark
```

Expected candidate baseline: all unit/integration tests pass and Voice benchmark is 6/6.

## 2. Capture/listen to the exact audio pipeline

Use the already saved HyperX input unless intentionally overriding it:

```powershell
python -m apps.voice_lab --audio-diagnostic --audio-diagnostic-seconds 8
```

During the 8 seconds:
1. stay quiet for about one second;
2. say: `Jarvis, tell me what the weather is supposed to be like tomorrow.` naturally;
3. stay quiet again.

Voice Lab prints the diagnostic folder under `.runtime\voice\diagnostics\<timestamp>\`.

Listen to:

1. `1_raw_device.wav`
2. `2_resampled_16k.wav`
3. `3_whisper_input.wav` (only created if speech evidence accepted a candidate)

Interpretation:
- raw is bad -> wrong Windows endpoint/device path or device-level issue;
- raw is clear but resampled is bad -> ORVEX resampler/input integration bug;
- raw + resampled are clear but exact STT input is clipped/wrong -> endpoint/VAD/evidence policy bug;
- all three are clear and Whisper is still wrong -> Whisper/provider quality/config becomes the leading issue.

`manifest.json` contains the evidence decision and metrics.

## 3. Silence false-trigger check

Start a 3-turn warm session:

```powershell
python -m apps.voice_lab --turns 3
```

Remain silent for several seconds before speaking. Tiny room/microphone events may print:

```text
Ignored non-speech candidate (...). Listening continues...
```

They must **not** produce a `You:` transcript or call Luna.

## 4. Clean-speech retest

In a quiet room, say three phrases naturally:

- `Jarvis, tell me what the weather is supposed to be like tomorrow.`
- `Can you remind me to call my mom when I get home?`
- `Open YouTube and search for relaxing music.`

Compare the terminal `You:` text to what was actually spoken.

## 5. Acceptance decision

- If the diagnostic WAVs expose corruption, repair the audio stage before evaluating STT providers.
- If the WAVs are clean and Whisper remains materially inaccurate, benchmark `gpt-transcribe` as a replaceable STT provider in a later repair/milestone.
