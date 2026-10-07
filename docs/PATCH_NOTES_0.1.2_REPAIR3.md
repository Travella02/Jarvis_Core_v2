# 0.1.2-repair3 — Pre-Speech Routing Gate

## Why Repair2 was not sufficient

Repair2 suppressed a delegation response as soon as a `delegate_to_jarvis_core` function-call event appeared. Live testing proved that boundary is still too late: Realtime could already begin WebRTC playback (for example, “let me think”) before the tool-call item reached the client. Clearing the output buffer after the function call only clipped the leak; it could not guarantee that zero pre-tool speech reached the user.

This is a provider-ordering problem, not a prompt-wording problem. Repair3 therefore stops trying to erase speech after it has started.

## V1 lesson reused

The V1 0.3.6 reference already established the stronger ownership rule: decide who owns a turn before allowing user-facing speech, and keep local/action/tool control traffic silent. In V1, completed input was routed through application/Core ownership before `response.create`, and silent actions cancelled/cleared provider output rather than treating generated narration as authoritative.

V2 keeps its current Realtime audio architecture, but ports that same invariant with a provider-supported response-level gate.

## Repair3 design

1. Every desktop user turn first creates an **internal routing response**.
2. That response is forced to call exactly one named function, `route_jarvis_turn`.
3. The routing response is explicitly **text-only** (`output_modalities=["text"]`), so it cannot create audible WebRTC output even if the model tries to add filler before the function call.
4. The router chooses one route: `direct`, `reasoning`, `memory`, `action`, `current_data`, `long_task`, or `sleep`, and preserves the actual user request.
5. `direct` returns immediately to Realtime for one normal audible answer.
6. Core-owned routes execute through the existing `DelegationOrchestrator`; only the verified result gets an audible response.
7. Every user-facing continuation is explicitly `output_modalities=["audio"]`, `tools=[]`, and `tool_choice="none"`. There is no second tool-selection opportunity that can prepend speech.
8. The renderer still suppresses/deletes any illegal message item from the internal router response as defense in depth.

## Tradeoff

Direct conversational turns now have one small silent routing inference before the audible response. This is a deliberate correctness tradeoff. Repair3 testing should measure whether that added routing hop keeps perceived latency acceptable. If it is too expensive later, the correct optimization is a trustworthy local/cheap pre-router—not returning to post-hoc audio suppression.

## Scope

This remains 0.1.2. It changes the control boundary around existing routing; it does not implement Memory 2.0, action execution, current-data tools, or durable background tasks.
