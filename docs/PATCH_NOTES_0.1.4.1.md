# 0.1.4.1 — Delegation guidance A/B (experimental)

Goal: compare existing Mini routing to an opt-in, slightly more explicit delegation rubric in a matched configuration. Earlier live testing found a complex local/cloud comparison could route direct and consume the 1,024-token mixed audio/text limit, while other complex questions successfully delegated. Repair14's compact-router experiment was rejected after route failures and slower median latency. This experiment does **not** reactivate compact routing or add Decisions API.

Changes:
- Opt-in `JARVIS_0141_DELEGATION_GUIDANCE` config, isolated to real Core/Luna overlap sessions.
- Matched baseline `mini-overlap-luna-trim` and guided `mini-overlap-luna-trim-guided` launchers. Only this env var differs.
- Guidance text is appended only to Mini's existing private **decision** prompt, not to speech generation, STT, Core calls, wake-only acknowledgment, or system actions. No keyword fast path.
- Offline privacy-conscious 12-prompt route/latency/core completion report; intentionally not an authority or accuracy oracle.
- Unit tests for all of the above.

Immutable behavior: 0.1.3 trimmed PCM, Mini model, reasoning effort, tool names, verified sleep evidence, private gate, Core authorization, Luna 1,024-token desktop setting, dry-run actions, and 8-second cancellation test.

Local results (Linux, reconstructed accepted 0.1.3 source): 784 tests run, 1 skipped, no failures. Actual Windows build and A/B routing accuracy, latency, voice reliability and cost remain unverified until user's live tests.
