# ISSUE_091 — 0.1.3 Repair13: silent PCM buffering adds response latency

## Evidence (user's Oct 12 live Repair12 Windows A/B)

Actual already-awake first-audio times stayed around 0.97–1.50 seconds. Mini route typically finished in approximately 0.42–0.75 seconds. The remaining 0.44–0.78 seconds was not distinguishable between provider synthesis arrival and PCM playback using Repair12's milestones. Decisions API shadow was often later than Mini routing because of transcription delay; therefore do not change routing authority.

## Hypothesis and source review

`pcmGateProcessor.js` queues *all* incoming WebRTC track samples immediately after `response.created`, including digitally silent frames while provider audio is pending. A speaker-authorized gate must play the queued silence first. An 8-second ring makes this particularly harmful for slower responses. This may explain part of the route-to-speech gap; real-world magnitude must be measured, not assumed.

## Repair13 opt-in experiment

- Keep baseline `mini-overlap-luna` unchanged by default.
- Add `mini-overlap-luna-trim` (same model / Luna / privacy / action dry run) with a provider-track **leading silence only** trim: drop pre-onset samples below amplitude 0.00015, preserving an 8 ms pre-roll and *all* pauses after onset. Retain 45ms post-onset start buffer.
- Keep all audio private until Mini's direct decision **and** confirmed same-turn transcript, or an already-Core-verified Luna voice result. Never modify the Decisions API, speech validation or tool permissions.
- Expose worklet callback milestones for PCM signal detected, threshold buffer ready, audio gate authorized, and first audible worklet frame. Measurements exclude hardware DAC/speaker transit latency.
- Fix missing underflow callback in old client integration so sparse diagnostics cannot trigger a JS error if a buffer underrun occurs.
- Standalone sample-level Node test verifies preauthorization silence, cancellation, sample continuity through post-onset pauses and removal of digitally silent queue in simulation.

## Acceptance blockers

Live Windows A/B still required. Must test wake, direct conversation, tool/Core/Luna delegation, sleep, interruption, clarity of low-volume utterances, music/audio continuity, and 20+ comparable already-awake direct turns per arm. If trim causes clipped consonants, missing audio, popping, underruns or incorrect responses, roll back to the original mode; do not commit.

## Explicitly out of scope

Identity/personality, Decisions authorization, routing prompt rewrites, removal of Core tool controls, changes to speech transcription, cache bypasses, TTS/model switching, real external actions, speculative audible speech before permission.
