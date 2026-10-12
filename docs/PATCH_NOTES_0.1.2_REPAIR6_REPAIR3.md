# Jarvis Core v2 0.1.2-repair6-repair3 — Sleep-intent evidence guard

## Live failure
After Repair6-Repair2, the natural closing utterance `Thanks Jarvis, that's all` routed to `sleep` as desired. However the standalone courtesy `Thanks Jarvis` **also** routed to `sleep` and closed the active conversation. This is a serious false-positive. The subsequent question with a follow-up request routed directly, so voice recognition isn't the cause.

## Fix (focused; no speculative-audio changes)
1. Retain the existing silent Realtime router. Clarify that politeness/gratitude and mention of Jarvis are **not** termination instructions. Provide contrastive examples.
2. Extend `route_jarvis_turn` with optional `sleep_evidence`: quote the exact portion of the user's speech that **independently** expresses a desire to end the interaction. Examples: `that's all`, `I'm done for now`, `Good night`. Gratitude itself must not be used as evidence.
3. Python bridge refuses to act on `route=sleep` lacking nonblank `sleep_evidence`, and instead continues with the normal direct Realtime reply. Logs `[Jarvis Route Guard] ... reason=missing_sleep_evidence` for diagnosis. Routing remains model-driven, not a hard-coded sleep-phrase fast path.
4. Updated existing bridge tests and new guard-focused tests. No changes to local wake, audio output, background-task policy, or parallel speculative candidates.

## Limitations
This is a **contract-level guard**, not an oracle: a model could still fabricate an incorrect closure evidence string because the accepted STT transcript may arrive asynchronously after route selection. In that case the guard alone cannot detect the fabricated quote. A more stringent future solution would validate evidence against the accepted transcript (with a sleep-only delay or provider-grounded evidence). Live acceptance must check the exact misclassified phrase and variations. Python regressions do not simulate the cloud model's semantic choices.

## Validation in reconstruction
- Focused 23 tests passed.
- Full suite: 551 tests, 1 existing skip.
- Diagnostics: Status: ok; desktop:check passes.
- Patch installer tested against exact baseline, Windows CRLF equivalence, second application and baseline mutation.

Stay on 0.1.2; no commit or patch cleanup until live acceptance.
