# 0.0.4-repair13 — Hybrid Speech Activity Recovery

## Problem
A live MME microphone could show strong levels in `--mic-test` while the normal Voice Lab remained listening forever because WebRTC VAD was the only signal allowed to start endpointing. In the observed Qwen A/B session a 90 ms VAD blip was rejected correctly, but later real speech was not reliably starting a candidate.

## Repair
- Add provider-neutral `SpeechActivityFusion` before endpointing.
- Keep raw WebRTC VAD telemetry honest; acoustic activity is a redundant fallback, not relabeled as VAD.
- Strong sustained speech may start/continue an utterance even when VAD is temporarily blind.
- Quiet/low-energy noise still cannot start a turn.
- `SpeechEvidenceGate` accepts either normal VAD-supported speech or conservative high-energy rescue evidence.
- Voice Lab prints when acoustic rescue is actually used.

## Non-goals
No STT/TTS/provider swap, no microphone-device change, no noise suppression/AEC, and no full-duplex changes.
