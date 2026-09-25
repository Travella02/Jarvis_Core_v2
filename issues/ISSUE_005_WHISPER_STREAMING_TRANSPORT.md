# ISSUE_005 — whisper.cpp Voice Lab transport is not the final streaming transport

## Version / candidate

0.0.4 - Voice Lab

## Symptom

The initial `WhisperCppProvider` uses a persistent localhost `whisper-server` and bounded rolling re-inference for partials. This lets us evaluate `large-v3-turbo-q5_0` quality and real latency without embedding whisper.cpp into Core, but an in-flight standard-library HTTP request cannot be hard-aborted portably.

## Expected behavior

0.0.4 must provide useful local streaming/partial transcription and discard cancelled results immediately. 0.0.5 barge-in must have measured, reliable cancellation and full-duplex behavior.

## Final fix

Keep the server transport entirely inside the adapter. Cancellation is monotonic and prevents stale results from reaching Voice Core. The contract permits replacing this transport later with a native binding or another STT provider without changing the ORVEX Voice Engine.

## Regression risk

Rolling re-inference may use more GPU than a true streaming decoder and may not hit the final latency target. That is a Voice Lab measurement, not an architectural commitment.

## Technical lesson

Use 0.0.4 to test model quality and architecture separately from the final optimized transport.
