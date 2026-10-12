# 0.1.2 Repair6-Repair7 — Tool-probe VAD lifecycle regression

## Problem
On Windows, `mini-tools` and `full-tools` showed accepted user transcripts with `turn=n/a` but never produced direct text answers or tool-selection events. The probe-specific event block returned early for all event types, including `input_audio_buffer.speech_started` and `input_audio_buffer.speech_stopped`.

## Fix
Allow those two VAD lifecycle events through to the established desktop lifecycle handler. The handler assigns turn IDs and sends one manually created response at speech stop. All generated text, tool requests, simulated outputs, and audio-denial events remain intercepted by the probe. No real Luna or computer actions are executed. No changes to the routed or fast conversation modes.

## Safety
No forced autoresponse or second response creation; no user-facing audio. Core remains authoritative. This is still a text-only, dry-run experiment, not a safe audible tool-enabled assistant.
