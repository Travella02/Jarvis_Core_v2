# ISSUE 107 — Natural-language tool capability and direct conversation regression

- Trigger: 0.1.5.2 Repair2 user observed normal conversation slowed, and natural long requests were rejected or appeared stuck.
- Cause: 0.1.5.2 gateway requires a whole-utterance `re.fullmatch` phrase and coordinator injects `{'site':'youtube'}` in lieu of model arguments.
- Approach: add a new opt-in semantic tool proposal and typed arguments, Core-enforced trusted evidence and whitelist, action-only validation, no extra general conversation classifier, strict A/B acceptance.
- Preserve: stable guided Realtime Mini, PCM trim, wake/sleep, direct speech, Core Luna delegation, dry-run tools, duplicate prevention.
- Safety limits: Core's lightweight veto remains conservative and may deny unusual valid phrasing; context-dependent search is not guaranteed. An independent semantic consent verification strategy is still needed before public release.
- Status: Candidate. Awaiting Windows build, real model routing, action UI, and direct latency validation.
