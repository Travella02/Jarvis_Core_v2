# ISSUE 058 — Realtime max_output_tokens clips spoken answers instead of making them concise

## Symptom
0.1.1 Repair4 raised the ordinary Realtime output ceiling to 320 tokens, but live testing showed normal answers ending mid-sentence. Telemetry reported `status=incomplete`, `output_tokens=320`, and `reason=max_output_tokens`.

## Cause
Realtime audio responses consume both text and audio output tokens. A hard token ceiling controls generation length, not conversational intent. It can stop audio at the token boundary before the model reaches a natural sentence ending.

## Repair5 decision
Do not use a small `max_output_tokens` value as the primary brevity mechanism. Keep Semantic VAD for endpointing, disable its automatic response creation in the desktop client, and have Jarvis explicitly send `response.create` for each completed user turn with response-specific compact-format instructions. Use 1024 normal / 2048 expanded only as generous runaway guardrails.

Jarvis Core owns the response policy and sends it to the thin renderer. Explicit depth requests can still use `request_expanded_response`. Core-delegated results receive the same compact spoken-surface policy.

## Architectural lesson
Provider token limits are safety guardrails, not a substitute for conversational orchestration. Keep response policy under Jarvis Core so it remains replaceable when the conversational provider changes.
