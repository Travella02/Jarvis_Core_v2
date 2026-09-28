# Jarvis Core v2 0.0.4 Repair34a — Whisper Final-Only Wiring Fix

Repair34 added the correct Whisper `emit_partials=False` behavior and CLI flag,
but the flag was accidentally applied in `doctor()` instead of the live
`build_engine()` path.

The live symptom was unambiguous:

- command included `--stt-endpoint-final-only`
- startup still printed `Whisper endpoint mode: rolling partial + final`
- turns still emitted `stt_first_partial`

Repair34a is a surgical wiring repair.

## Changes
- Adds one `_whisper_config_from_args(...)` helper.
- `build_engine(args)` now constructs the live Whisper provider from that helper.
- `provider_health(args)` uses the same helper.
- `doctor()` uses the helper without arguments and no longer contains the
  accidental undefined `args` reference.
- No Whisper model/audio settings change.
- No Luna/Qwen/personality/whole-response/fixed-seed/playback change.

## Expected live confirmation
With `--stt-endpoint-final-only`, startup must print:

`Whisper endpoint mode: final-only after endpoint`

Measured turns should no longer contain an `stt_first_partial` latency mark.
