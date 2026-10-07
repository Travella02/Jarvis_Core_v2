# ISSUE 065 — Realtime pre-tool audio can escape before delegation is observable

## Live evidence

After 0.1.2-repair2, the reasoning-delegation test still audibly began with “let me think”. Playback was then cut after “think” when the later delegation event caused Repair2 to mute/clear the buffer. The final Core answer was correct. The background-task test passed because that particular turn emitted the tool call early enough.

## Root cause

Repair2 used `response.output_item.added` / `response.function_call_arguments.done` as the earliest moment to identify a delegation response. That is not an ownership boundary: Realtime may generate and start playing a message item before it emits the function-call item. Once WebRTC audio has reached the speaker, cancelling or clearing later can only truncate the leak.

Prompting the model to put a tool call first is therefore insufficient as a hard invariant.

## V1 comparison

The V1 reference did not rely on discovering ownership after speech had begun. Its desktop flow resolved/routed recognized turns before creating the user-facing response, and its silent-action repairs cancelled/cleared automatically created output. Later V1 repairs also bound interruption/mute state to provider response IDs.

## Repair3 resolution

Move route selection ahead of audible generation. The first desktop response is forced to `route_jarvis_turn` and is text-only. Only after that route is known may an audio response be created. Final audible responses have tools disabled.

This removes the race instead of trying to win it.
