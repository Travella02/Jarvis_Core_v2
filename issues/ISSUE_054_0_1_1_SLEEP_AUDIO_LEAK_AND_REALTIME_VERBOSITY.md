# ISSUE 054 — 0.1.1 sleep audio leak and Realtime verbosity

## Observed
During live 0.1.1 acceptance, a repeated explicit sleep request could allow a fragment of Realtime speech to become audible before the desktop entered local sleep. The sleeping UI also retained the last visible response. Separately, short conversational follow-ups could produce unnecessarily long spoken paragraphs despite the intended concise conversational style.

## Cause
The desktop waited for the lifecycle command and then tore down the WebRTC session, but it did not synchronously silence the local audio element and clear/cancel provider output before teardown. The Realtime prompt also described concise speech only broadly, without a concrete conversational-length policy for ordinary follow-ups.

## Repair
0.1.1 Repair1 makes clear sleep intent tool-only, immediately cancels/clears provider output, pauses/mutes local playback before transport teardown, clears visible captions on sleep, and restores audio on the next session. Realtime direct answers now default to one to three natural sentences for ordinary questions while explicitly preserving personality and allowing longer answers when requested or genuinely needed.

## V1 lesson carried forward
V1's accepted sleep path cancelled the active response, cleared output/input audio buffers, muted/paused remote audio, and entered sleep silently. This repair carries that proven boundary forward without reintroducing V1 coupling.
