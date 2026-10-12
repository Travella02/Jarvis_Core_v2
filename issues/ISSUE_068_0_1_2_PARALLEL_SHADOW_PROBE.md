# ISSUE 068 — Safe parallel candidate experiment

**Status:** Repair6 live validation pending. Not production ready.

Repair5 direct spoken replies are slowed by the sequential cloud routing gate. Simply starting another WebRTC audio response could leak unauthorized words, corrupt captions, or collide with Core result speech. This issue captures the experimental non-user-facing concurrency probe, leaving safe routing and one audible response unchanged.

Acceptance: all baseline regressions remain green; opt-in Realtime out-of-band candidate is text-only, no-tools and conversation-none; Luna shadow uses no tools and cannot mutate history; cancellation and turn matching are per-response; telemetry exposes time-to-transcript, first token and cancellation; live evidence determines whether a future buffered-audio stage is worthwhile.
