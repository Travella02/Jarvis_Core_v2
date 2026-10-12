# ISSUE 074 — Gate-free tool choice without premature speech

## Risk
The WebRTC audio media track can output model speech before a late function call event. Earlier repair iterations demonstrated premature, contradicting acknowledgements. Audio muting when a call arrives is too late.

## Probe scope
Test Realtime Mini/Full tool_choice=auto in text-only mode. Validate correct direct vs ask_luna vs simulated action selection, event timing and API estimates. Never execute operations or publish audio while tool selection is unresolved.

## Deferred engineering
Actual tool-capable live audio needs a protected response-specific pre-publication boundary and authoritative tool results, plus end-to-end verification. No prompt-only guarantee is sufficient.
