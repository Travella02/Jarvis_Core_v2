# Jarvis Core v2 0.0.5 Repair5f — Voice Lab confidence callback scope fix

## Symptom

The first live Repair5e Voice Lab launch failed immediately with:

`NameError: name 'on_confirmed' is not defined`

## Cause

Repair5e added the new confidence diagnostic callback inside
`_run_legacy_session()`, but the normal continuous `run_session()` subscribed to
that callback without defining it in its own local scope.

The automated confidence/engine tests passed because they exercised the speech
validator and engine directly rather than the normal Voice Lab session startup.

## Fix

The continuous Voice Lab path now defines its own:
- rejected-candidate confidence logger;
- confirmed-speech confidence logger;
- existing acoustic-rescue logger.

No speech thresholds, confidence weights, Silero behavior, Whisper behavior,
wake/sleep behavior, interruption policy, Qwen behavior, or Luna behavior changed.
