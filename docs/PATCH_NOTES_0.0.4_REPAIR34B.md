# Jarvis Core v2 0.0.4 Repair34b — Stale Regression Assertion Fix

Repair34a correctly moved Whisper final-only selection into the shared
`_whisper_config_from_args(...)` helper and wired live `build_engine(args)`
to that helper.

One older Repair34 source-regression test still looked for the pre-refactor
implementation detail `replace(stt_config, emit_partials=False)`. That exact
string no longer exists after Repair34a even though the functional behavior
is correct.

Repair34b changes only that stale test assertion. It now verifies that the
live Voice Lab code still exposes `--stt-endpoint-final-only` and routes the
live engine through `_whisper_config_from_args(args)`.

No runtime code, Whisper settings, Luna, Qwen, voice behavior, latency behavior,
or application logic changes in Repair34b.
