# ISSUE 028 — 0.0.5 duplicate speech authority and silence hallucinations

## Observed

Repair3 live testing still failed in two directions:

- legitimate speech was often missed or fragmented;
- silence/background activity was transcribed as phrases such as `Thank you`,
  `Bye`, or `Wow`, creating false user turns and even interrupt/reply loops.

## Reference-project finding

Inspection of the clean V1 0.3.6 checkpoint showed that V1 deliberately kept
Realtime VAD/transcription as a **single speech-turn authority**. VAD start was
provisional, transcript evidence could confirm a barge-in, and transcript-less
false-VAD turns were recovered instead of becoming permanent conversation turns.
V1 explicitly avoided introducing a duplicate recognizer for interruption.

## Root cause in Repair3

Core v2 still split ownership:

- endpoint/evidence logic decided candidate validity;
- a second bounded Whisper probe independently tried to confirm interruption;
- the final STT pass was another recognition boundary.

Local Whisper is also more susceptible than the old hosted Realtime transcriber
to silence hallucinations, so any extra recognition path increased the chance of
a false semantic event.

## Repair4

- one live Whisper turn receives the candidate audio as it arrives;
- partial and final text from that same turn are the semantic speech evidence;
- no duplicate interruption recognizer remains;
- transcript-less candidates reset inside the same microphone stream;
- arbitrary early partials require same-stream stability unless they are an
  explicit control/follow-up word;
- whisper.cpp native non-speech suppression is enabled with `suppress_nst` and
  `no_speech_thold`;
- amplitude remains diagnostic/candidate evidence only, never the final speech
  authority.

Status: fixed in 0.0.5 Repair4 candidate; requires live acceptance.
