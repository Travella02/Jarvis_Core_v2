# ISSUE 071 — Standalone gratitude misclassified as sleep

**Observed**: 0.1.2-repair6-repair2 live test: model router chose `route=sleep` for "Thanks Jarvis" without a dismissal. User explicitly confirmed it put Jarvis to sleep. "Thanks Jarvis, that's all" correctly slept; follow-up question remained direct. The previous correction relied solely on prompt wording despite a negative instruction already present.

**Repair6-Repair3**: A structured field `sleep_evidence` is requested only when clear end-of-interaction words independently exist; no evidence means the bridge refuses a `sleep` transition and selects a normal direct response. Contrastive examples in router instructions emphasize standalone courtesy is not lifecycle control. No phrase-specific shortcut.

**Residual risk**: Incorrect but nonempty evidence is not verified against asynchronous transcription. This repair improves defensiveness but does not prove a zero-false-positive classifier. Observe actual tool arguments and repeat live tests.
