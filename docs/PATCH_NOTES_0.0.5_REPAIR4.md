# Jarvis Core v2 0.0.5 Repair4 — V1-Style Single Transcript Authority

## Why Repair3 failed live

Repair3 moved the decision away from raw loudness, but it still had two competing
speech-recognition paths:

1. endpoint/evidence logic created and rejected candidates before the final turn;
2. a separate bounded Whisper snapshot tried to prove an interruption early.

That created exactly the kind of split ownership the V1 project had already
learned to avoid. The live symptoms were repeated quiet-speech misses plus local
Whisper silence hallucinations such as `Thank you.` becoming false user turns and
interrupting Jarvis.

## What the V1 reference project actually did

Repair4 was designed after inspecting the clean V1 0.3.6 checkpoint, especially:

- `ISSUE_270_DEDICATED_SPEECH_COULD_NOT_BE_INTERRUPTED_NATURALLY.md`
- `ISSUE_271_WAKE_FIRST_RESPONSE_GATE_BLOCKED_BARGE_IN.md`
- `ISSUE_337_CONNECTED_ACTION_UNKNOWN_DECISIONS_AND_FALSE_VAD_STUCK_THINKING.md`
- `ISSUE_339_LONG_TRANSCRIPTLESS_VAD_COULD_STILL_STRAND_THINKING.md`
- the Realtime event handling in `apps/desktop/lab/app.js`

The important V1 rule was not a magic volume threshold. VAD opened a provisional
microphone turn, but one transcription stream owned semantic speech evidence.
False VAD starts without transcript evidence received bounded recovery instead of
becoming permanent user turns. Transcript evidence could confirm a real barge-in,
and stale work was prevented from resuming afterward.

## Repair4 architecture

Core v2 now follows that ownership model locally:

- VAD/adaptive activity only opens a **provisional candidate** and provides
  endpoint boundaries. It is not proof that the user spoke.
- That candidate is fed continuously into **one local Whisper STT turn**.
- The same STT turn produces rolling partials and the final transcript.
- There is no second `_probe_lexical_text` recognizer request.
- A meaningful same-stream partial can confirm barge-in while Jarvis is thinking,
  synthesizing, or speaking.
- Arbitrary partial phrases need stability with another same-stream partial before
  early cancellation; deliberate controls/follow-ups such as `wait`, `stop`,
  `actually`, and `why` can confirm immediately.
- If a candidate ends without transcript authority, it is discarded and capture
  continues on the **same open microphone stream**. The device is not reopened and
  no pending STT task is leaked.
- Quiet speech is not vetoed by RMS or peak level. Sustained WebRTC VAD or
  compatible Whisper partial/final evidence can validate the final transcript.
- RMS/peak stay telemetry only.

## Whisper silence-hallucination suppression

The whisper.cpp adapter now sends the server's native:

- `suppress_nst=true`
- `no_speech_thold=0.60`

These are model-side non-speech controls, not microphone-volume gates. Their job
is to make silence/noise more likely to return no transcript rather than common
hallucinated phrases.

## `--stt-endpoint-final-only`

For normal 0.0.5 continuous conversation, internal Whisper partials are now
required as the local speech-turn authority. The flag still means **only the
final transcript is submitted to Luna**; intermediate partials remain local and
are used only for endpoint/barge-in decisions. Legacy half-duplex mode can still
run true one-shot final-only STT for A/B testing.

## Scope

Repair4 does not change Luna, Qwen voice quality, personality, wake phrases,
sleep timeout, or interruption context accounting. It changes only who owns the
decision that a microphone candidate is a real user turn.
