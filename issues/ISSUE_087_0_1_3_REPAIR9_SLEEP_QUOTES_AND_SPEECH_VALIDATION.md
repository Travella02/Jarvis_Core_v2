# ISSUE 087 — Repair9: Sleep evidence mismatch and phantom direct audio

Status: Candidate; requires local Windows live acceptance.

## Evidence

Repair8 correctly protected against an unsupported `sleep_jarvis` function call,
but **rejected legitimate voice dismissal twice** with `sleep_evidence_mismatch`,
including confirmed transcripts `That's all Jarvis` and `that's all Jarvis, that's`.
The logs did not include the model's sleep_evidence string, so it was impossible
to determine the exact mismatch. A separate post-microphone-bump turn produced
an `Uh-oh` spoken answer without confirmed user transcript.

## Repair9

- Retain strict same-turn and committed-audio-item identity for sleep authorization.
- Continue using Mini's normal *semantic* tool selection. No hard-coded sleep
  word/phrase routing or alternative NLP shortcut is introduced.
- Compare the normalized quoted evidence flexibly: ignore wake word, accept
  verbatim phrases or a shared ordered two-word span with majority token overlap.
  Guard mismatched negation, wrong turns, empty words and unrelated evidence.
- Request a **verbatim quotation** rather than a paraphrase in Mini's tool instructions.
- Emit `sleep_evidence_check` telemetry showing the actual model quote and
  confirmed text (short diagnostic snippets) and the same-binding result.
- For an ordinary direct voice response, keep private PCM gated until the same
  audio item's transcript contains substantive words. A semantic-VAD/noise
  event without confirmed content cannot publish audio or reply text.
  Typed input remains immediately confirmed. Core-approved Luna responses are
  unaffected. Unresolved direct turns fail closed after 2.5 s and stay READY.
- If an unconfirmed speculative response reaches its output limit, discard its
  partial content safely instead of publishing speech or taking the desktop offline.
- No changes to the audio engine, PCM worklet, wake listener, Core provider,
  Luna, Decisions, external actions, personality or global response-length rules.

## Tradeoffs / limits

The direct speech guard **may increase perceived response latency** when
Realtime transcription arrives later than the Mini decision, and may drop short
legitimate interjections with insufficient speech evidence. Verify this live.
Neither text matching nor transcription can prove who physically spoke; a
credible hallucinated transcript is still an upstream speech-validation issue.
The overlap quote verifier is not a substitute for semantic intent classification.

## Live acceptance

1. Speak `That's all, Jarvis` and verify `sleep_evidence_check approved=true`,
   then `phase=sleep` and wake detection resumes.
2. Wake, speak `Thanks, Jarvis` and remain awake.
3. Bump the microphone without speaking and verify no audible invented answer.
   An unconfirmed noise-triggered turn should produce
   `phase=unconfirmed_direct_discarded` without OFFLINE.
4. Test direct math twice; record first-audio latency and verify no additional
   delay deemed unacceptable. Check voice naturalness and full captions.
5. Type `That's all, Jarvis` and verify typed sleep still works.
6. If sleep still rejects, provide `sleep_evidence_check` and relevant
   `USER SPEECH` lines; do not blindly broaden the match.

Keep patches/backups; no cleanup or commit until user accepts live validation.
