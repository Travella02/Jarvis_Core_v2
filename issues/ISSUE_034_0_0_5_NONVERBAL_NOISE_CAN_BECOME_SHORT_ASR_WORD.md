# ISSUE 034 — Nonverbal speech-like noise can become a short ASR word

## Observed

After independent Silero speech presence eliminated repeated silence hallucinations, live testing showed that microphone rubbing and sneezing could still be classified as speech-like audio. Whisper could then produce a short lexical hallucination such as `you`, causing the candidate to become a user turn.

## Why this is different from the old ghost-transcript bug

Silero is doing its job: some nonverbal human sounds are acoustically speech-like. Whisper is also being asked to decode difficult audio and can emit a plausible short word. A binary VAD decision plus lexical text therefore remains insufficient for turn ownership.

## Repair5e

Introduce a provider-neutral multi-signal confidence layer using Silero probability, ASR confidence, rolling transcript stability, and duration. Silero remains candidate detection only. No keyword allow-list/deny-list or semantic shortcut is introduced. One-word answers remain valid when their evidence is strong.
