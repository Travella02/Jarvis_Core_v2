# Jarvis Core v2 0.0.5 Repair3 — Lexical Speech Authority + Reliable Barge-In

## Live failure

Repair2 still treated acoustic/VAD confirmation as the authority for interruption.
On the user's headset, real quiet speech was repeatedly rejected as
`insufficient-energy` / `peak-below-threshold`. A false active-turn confirmation
could also cancel a Luna/Qwen response before playback, producing a generated
answer with `Playback: queued=0` and `heard=[none]`.

## Repair3 policy

Speech legitimacy is now decided by **local STT words**, not amplitude.

- VAD/activity remains responsible for locating candidate audio boundaries.
- RMS, peak, and adaptive noise-floor values remain telemetry only.
- Quiet endpointed candidates are allowed to reach local Whisper.
- A completed candidate is accepted when Whisper returns lexical text.
- Empty/non-lexical Whisper output is ignored and listening resumes.
- Active-turn interruption listens for `voice.speech.lexical_confirmed`.
- Raw `voice.speech.started` / activity confirmation never cancels Jarvis.

## Early barge-in

While Jarvis has an active response, VoiceEngine may run a bounded local-Whisper
snapshot after enough VAD speech has accumulated. This can confirm real words
before the user's complete utterance endpoints.

Early confirmation is intentionally conservative:
- two or more lexical words confirm interruption;
- deliberate one-word controls/follow-ups such as `stop`, `wait`, `why`,
  `actually`, `cancel`, `pause`, `no`, or `Jarvis` can confirm;
- common short silence hallucinations do not cancel early.

The full utterance keeps recording after early confirmation and its final
transcript becomes the next conversational turn.

If the early probe does not confirm, the final lexical transcript still cancels
an active response. This preserves cancellation while Jarvis is thinking,
synthesizing, speaking, researching, or working once those future modes register
under the same interruption contract.

## Expected effect

A quiet phrase such as `Why is that?` should no longer be discarded because its
peak RMS is low. Background activity with no legitimate local-STT words should
not cancel a response. A response that wins the race against noise should proceed
to Qwen and playback rather than ending as an unheard interrupted turn.
