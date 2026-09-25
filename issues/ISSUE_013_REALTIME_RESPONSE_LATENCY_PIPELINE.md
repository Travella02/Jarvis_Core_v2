# ISSUE_013 — Realtime response latency pipeline

## Status
Addressed in 0.0.4-repair8 candidate; live acceptance pending.

## Observed live behavior
On the accepted repair7 runtime, the first real HyperX/RTX 5080 turn measured approximately:

- endpoint -> STT final: 93 ms
- STT final -> Luna first text: 3219 ms
- Luna first text -> Chatterbox first audio: 2438 ms
- speech end -> first audible audio: 5796 ms

Whisper Q5 was already fast enough to stop treating STT as the primary latency problem. The remaining latency was intelligence time-to-first-text plus the response chunking/TTS path.

## Root causes / design gaps

1. Normal Conversation Core defaults still used a higher reasoning policy than desired for ordinary Jarvis turns.
2. The first TTS chunk could wait too long for a full sentence/large phrase.
3. TTS synthesis and physical playback were serialized; the next phrase did not synthesize while the current phrase was playing.
4. Display markdown could leak into spoken text.
5. Existing telemetry combined chunk-wait and synthesis time, making the Chatterbox cost ambiguous.

## Repair8 policy

- Luna defaults to provider-neutral `none` reasoning with no automatic reasoning escalation in the current product path.
- Future difficult-task routing to a stronger provider (for example Sol) remains a provider-routing milestone, not a reason to make Luna think longer by default.
- Voice turns get a provider-neutral concise spoken-response instruction.
- Core uses a smaller latency-first opening phrase, then larger later phrases.
- Intelligence text streaming, TTS synthesis, and audio playback run through independent queues so later phrases can synthesize while earlier audio is playing.
- A Core-owned speech normalizer strips deterministic display markup before TTS without changing the authoritative/display response text.
- Telemetry now separates first model text, first speech chunk, first TTS request, first waveform, and first device write.

## Acceptance target
The repair is not accepted based on architecture alone. Re-run the same real microphone test and compare stage timings. If Chatterbox inference remains too slow after chunking delay is isolated, replace/optimize the TTS adapter rather than hiding the result.
