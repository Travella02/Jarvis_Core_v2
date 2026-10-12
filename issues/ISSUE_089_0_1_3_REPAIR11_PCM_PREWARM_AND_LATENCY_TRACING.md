# 0.1.3 Repair11 — Realtime Mini direct speech latency regression

## Evidence
Repair10 Windows voice tests observed end-of-speech to first audio approximately 1.16 to 2.39 seconds for direct, already-awake and wake-and-command turns. A prior 0.1.2 baseline sometimes produced roughly 0.7–1.1 seconds. These runs were not controlled head-to-head comparisons and should not be treated as distribution estimates. User's desired engineering target: already-awake, direct answers ~500–800 ms, preserving expressive natural voice, wake/sleep validation, and tool safety.

## Plausible local overhead found in source
Each approved overlap candidate used to construct a new AudioContext and load an AudioWorklet module before it could authorize PCM. This is redundant per turn. Independent text-only Mini classification and Realtime audio synthesis are still material sources of latency, so prewarming alone cannot guarantee the target.

## Narrow experiment
- Prewarm one silent AudioContext and the PCM processor module after the WebRTC remote track appears, without attaching provider audio, resuming playback, or authorizing the gate.
- Reuse the module/context, but create a **new, private worklet and sample buffer for every response**. Disconnect and abort each gate upon cancellation. Only an authenticated direct/same-turn result may authorize; Luna and sleep rules stay unchanged.
- Emit `[Jarvis Latency Detail]` from the first actual audible audio frame, via the desktop host: committed input, transcript, route decision, candidate creation, PCM readiness, gate authorization and first audio, relative to speech stopped.
- Report silent prewarm ready/failure, but do not stall session launch on either. Failed prewarm must use existing normal failure handling; it must not unmute provider audio.

## Acceptance criteria
Run >=20 already-awake direct spoken turns in the Repair11 candidate and compare with the 0.1.2 release under comparable hardware/network conditions: median <=800 ms is the goal, 90th percentile <=1.3 s is a stretch goal. Track wake turns and Luna separately. Verify no pre-tool speech, no speaking during mic bumps, no phonetic-triggered accidental sleep, clean uninterrupted PCM and truthful Core tool routing. Do not claim latency targets met until measured on Windows.

## Scope deferred
No changes to Mini model/tool choice, response length, natural voice prompt, Decisions API, Luna reasoning, or sleep-evidence policy. If improvement is small, analyze phase timings; a future routing-architecture A/B experiment would be required to beat a >500 ms selection consistently.
