# ISSUE 015 — Audio Input Validation & False-Speech Rejection

## Observed

During 0.0.4 live testing on the saved HyperX headset microphone, quiet-room runs produced endpointed turns and Whisper transcripts such as `Thank you.` when the user had not spoken. Clean speech was also frequently transcribed incorrectly.

## Risk

Treating WebRTC VAD as final authority allows clicks/noise/low-information audio to reach a generative STT model, which can return plausible language for non-speech. Swapping STT providers before validating raw/resampled audio could hide an ORVEX input bug instead of fixing it.

## Repair10 response

- VAD becomes one signal in a provider-neutral speech-evidence gate.
- Audio must also satisfy duration, ratio, energy, peak, and adaptive noise-floor checks.
- Rejected candidates never reach STT and do not become conversation turns.
- Diagnostic WAV capture exposes native input, resampled input, and exact accepted STT bytes for human listening.

## Follow-up

Final noise suppression, AEC, gain strategy, and full-duplex barge-in remain 0.0.5 work. Cloud STT fallback remains possible behind `SpeechToTextProvider` if clean-audio Whisper testing still misses the product quality bar.
