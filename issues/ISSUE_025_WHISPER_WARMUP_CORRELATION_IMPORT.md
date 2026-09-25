# ISSUE 025 — Whisper warmup missing CorrelationContext import

## Symptom
Voice Lab repair19 startup stopped during provider prewarm with `NameError: name 'CorrelationContext' is not defined`.

## Root cause
`WhisperCppProvider.warmup()` constructs a hidden `AudioFrame` using `CorrelationContext.create()` but repair19 did not import `CorrelationContext` in that provider module. Unit coverage verified structure and policy but did not execute this exact warmup path.

## Repair
Import `CorrelationContext` from `core.common.ids` and add an executable warmup regression test.
