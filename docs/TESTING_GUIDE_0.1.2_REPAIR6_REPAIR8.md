# 0.1.2 Repair6-Repair8 — Buffered-Audio Tool Selection Experiment

## What this is
- This is an **opt-in developer experiment**. Run `python scripts/realtime_ab.py mini-buffered`.
- Keeps Realtime Mini as the frontend, and **the normal audio WebRTC track is muted from first attachment**.
- Captures each Realtime response privately with MediaRecorder and decides only after `response.done` whether it contained tool calls.
- Direct reply: once the provider audio buffer drains, plays the captured response as an ordinary recording and publishes the matching transcript.
- Tool request: discards all pre-tool audio/text. Returns a *simulated* unavailable/not-executed tool result and requests one tool-disabled spoken reply.
- No real Luna invocation and no real computer actions; this is deliberately isolated from Core executors. Safe-routed and fast-direct modes remain intact.
- Any interrupted/canceled/failed response or unsupported recording format remains silent. Buffers are bounded to 30 seconds and cleaned up on interruption and shutdown.

## Important tradeoff
An unrestricted model may produce some speech before deciding to call a tool. To guarantee **zero** premature audio, this experiment waits for **the entire tool-capable response** before releasing direct audio. It is not expected to match the prior 498 ms gate-free time. These measurements determine whether the architecture is viable; no production performance guarantee.

## Commands (one at a time)
`python -m unittest tests.unit.test_0_1_2_repair6_repair8_buffered_voice -v`
`python -m unittest discover -s tests -v`
`python -m core.diagnostics`
`npm run desktop:check`
`python scripts/realtime_ab.py mini-buffered`

## Live spoken tests and pass conditions
1. **Say:** “Jarvis, what planet is known as the Red Planet?” — **Expected:** one complete audible direct answer and matching caption, no tool.
2. **Say:** “Jarvis, analyze event sourcing tradeoffs for a complex distributed system.” — **Expected:** `ask_luna` selected, `pretool_audio_not_authorized` log, only one audible *simulation* explanation, no claim Luna actually ran.
3. **Say:** “Jarvis, start a background build while I'm gone.” — **Expected:** `test_action` selected; nothing starts; no premature "starting it" audible; one truthful audible simulated-unavailable reply.
4. **Say:** “Jarvis, what is seventeen times six?” — **Expected:** 102, no tool, full captions.
5. **Interrupt during any spoken buffered reply**, or close Jarvis mid-turn — **Expected:** playback stops immediately, stale audio never replays.

## What to send back
- `[Jarvis Buffered Audio]`, `[Jarvis Tool Probe]`, `[Jarvis A/B Usage]`, `[USER SPEECH]`, `[JARVIS REPLY]` and `[Desktop latency]` lines.
- Whether complete audio actually played, whether the first word was clipped or delayed, whether audio was doubled, any model errors.
- A comparison of first audible playback with the original `mini-fast` 498 ms reference.

## Safety and workflow
- Do not add real tools or use this opt-in experiment with user data or unattended tasks.
- Preserve V1 as read-only reference; the trusted Core executor remains authoritative.
- Do not clean patches or commit until live acceptance.
