# ISSUE-012 - Audio Device Native Rate & Response Warmup

## Discovered
0.0.4 live acceptance on Windows / HyperX Cloud Alpha Wireless.

## Symptoms
- OS default input captured room/TV audio instead of the intended headset microphone.
- Explicit headset endpoint failed with PortAudio `Invalid sample rate` because the integration forced 16 kHz device capture.
- First successful turn measured roughly 22 seconds from Luna first text to Chatterbox first audio because Chatterbox model loading occurred only when synthesis began.

## Root causes
1. Hardware sample rate was coupled directly to Voice Core's 16 kHz processing format.
2. Voice Lab did not identify/persist the selected physical endpoint.
3. Provider startup/model-load time occurred inside the first user turn.

## Repair7 policy
- Device-native capture belongs to the audio integration; Core/STT keep the stable 16 kHz contract.
- User can verify/select/persist the physical endpoint; hardware detection remains recommendation-only.
- Local providers are loaded before Voice Lab starts listening so response telemetry measures conversational work, not process/model startup.

## Future work
0.0.5 may replace the simple integration-local resampler with a production native/DSP path while preserving the same Core contract. Full-duplex/AEC/barge-in and provider-native streaming remain separate milestones.
