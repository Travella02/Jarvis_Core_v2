# 0.1.2-repair2 — Silent Delegation Boundary & Internal-Routing Suppression

## Why Repair1 was not enough

Repair1 correctly tightened the prompt and stopped caption truncation, but live testing proved the provider could still emit spoken pre-tool commentary before `delegate_to_jarvis_core`. Two failures remained:

- reasoning delegation could announce internal routing such as “let me pull in the Core”; and
- an unsupported background task could still say “let me get that started” before the authoritative unavailable result arrived.

Repair1 also made generated pre-tool transcript text suddenly appear when the function call boundary was reached, which exposed exactly the internal speech we do not want users to see.

## Repair2 behavior

Repair2 stops treating pre-tool speech as user-facing content at all.

- The earliest observed `response.output_item.added` function-call event marks the current delegation response as suppressed.
- The desktop immediately mutes remote audio and clears the provider output-audio buffer for that suppressed response.
- Any transcript deltas and later output-buffer events belonging to the suppressed response are ignored.
- Generated assistant message items attached to the suppressed delegation response are removed from Realtime conversation history after `response.done`, so false pre-tool progress does not become future conversational context.
- The next post-tool response gets a new response ID and restores normal audio/caption presentation.
- User-facing prompt rules now explicitly forbid narrating Core, delegation, backend routing, tools, models, or providers unless the user is directly asking about Jarvis architecture.
- Phrases such as “use your Core” are treated as an internal routing preference, not something Jarvis should echo back to the user.

## V1 lessons reused

The read-only V1 0.3.6 checkpoint was rechecked before this repair. Repair2 ports the same two boundaries that proved important there:

1. response ownership is tracked by response identity so stale/suppressed provider events cannot resume audio or mutate the current visible answer; and
2. provider-generated speech that does not own the final authoritative result may be cancelled/cleared rather than preserved for presentation.

V2 keeps the implementation smaller: only delegation preambles are suppressed, while ordinary Realtime answers remain fully streaming.

## Scope

Repair2 does **not** implement background tasks, actions, current-data lookup, or Memory 2.0. Those capability slots remain fail-closed exactly as 0.1.2 intended.
