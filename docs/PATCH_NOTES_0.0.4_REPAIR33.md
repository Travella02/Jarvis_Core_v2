# Jarvis Core v2 0.0.4 Repair33 — Whole-Response TTS A/B

Repair31 is the committed fast/consistent separate-sentence baseline.
Repair32 improved pauses but sentence-to-sentence Qwen generations can still
shift slightly in voice and delivery.

Repair33 is a controlled A/B. It does NOT reduce Jarvis's personality,
humor, comments, reaction style, or response freedom.

## Modes

`--tts-response-mode streaming`
- default;
- exact Repair31 scheduling behavior;
- Luna text chunks become separate TTS requests;
- lowest time-to-first-speech.

`--tts-response-mode whole`
- Luna is allowed to finish its complete natural response;
- that entire response is normalized once and sent to Qwen in one request;
- Qwen still streams PCM immediately after that one request starts;
- fixed-seed Repair31 behavior remains available.

## Humanization rule

Repair33 changes TTS scheduling only. It does not add a one-sentence or
two-sentence cap, does not force terse replies, and does not alter
`VOICE_RESPONSE_INSTRUCTION` or ConversationCore personality behavior.

Jarvis remains free to be conversational, humorous, reactive, and to elaborate
when useful. The experiment measures the latency cost of giving Qwen the whole
thought so it can produce continuous prosody.

## New latency marks

- `luna_response_complete`
- Luna first text -> Luna response complete
- Luna response complete -> TTS request

These isolate the exact price of waiting for the complete response.

## Acceptance

Whole mode is worth keeping if voice continuity/prosody improves substantially
and first audible response remains subjectively fast enough. The goal is not
an arbitrary benchmark; it is fast, natural conversation.
