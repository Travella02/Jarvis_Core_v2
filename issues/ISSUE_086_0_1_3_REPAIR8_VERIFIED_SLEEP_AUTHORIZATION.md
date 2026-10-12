# ISSUE 086 — Sleep tool call accepted without confirmed current-turn speech

Status: Repair8 candidate, live acceptance pending.

## Reproduction

A microphone bump created an extra Realtime audio turn. The silent decision
selected `sleep_jarvis`, providing generated `sleep_evidence`; no matching
`[USER SPEECH]` confirmation was seen. The client entered sleep anyway.
Existing Repair15 validated that evidence was a nonempty tool argument, but did
not cross-check the confirmed user words or audio item ID.

## Repair8

* Sleep intent remains natural model classification, never a keyword shortcut.
* A sleep tool call cannot authorize itself: its quotation must match words in
  the exact *confirmed* current-turn transcript (or a submitted text/wake
  command). Whitespace and punctuation may differ; wake-word-only evidence
  never suffices. No second model or extra API cost.
* Audio binding uses committed Realtime item ID rather than a guessed turn.
  Late transcripts from older audio items can never approve new-turn sleep.
* If the decision arrives before transcription, keep speculative audio private,
  wait up to 2.5 seconds for the matching transcript, then reject unresolved
  sleep safely. Ordinary direct conversations have no extra wait.
* New speech/typed input cancels the pending sleep decision; stale timers
  cannot trigger the lifecycle after cancellation or session shutdown.
* Mic feedback that Realtime *transcribes* as a plausible closing phrase may
  still require upstream speech-validity tuning later; STT corroboration is not
  a cryptographic proof of human intent.
* No changes to PCM worklet, wake recognizer, response-length policy, Luna,
  Decisions routing, actual actions, memory, or provider permissions.

## Live acceptance

Run focused/full tests and launch `mini-overlap-luna` or
`mini-overlap-luna-cancel-test`.
1. Wake and say `Thanks, Jarvis.`; remain awake.
2. Say `That's all, Jarvis.`; sleep after confirmed speech.
3. Wake with `Hey Jarvis, what's nine times eight?`; answer 72.
4. While awake, make a harmless mic bump without words; no sleep.
5. If a false sleep selection appears, check for `sleep_pending_confirmation`
   followed by `sleep_rejected`, not `phase=sleep`. If confirmed STT incorrectly
   transcribes a dismissal, capture the actual transcript separately.
6. Type `That's all, Jarvis.` while awake; sleep immediately without STT wait.

Keep patch and backup files until live acceptance; do not commit yet.
