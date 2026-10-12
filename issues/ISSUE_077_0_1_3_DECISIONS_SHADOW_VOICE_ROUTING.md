# Issue 077: Decisions API may be a cheaper/faster decision provider, but is not audio-native

Accepted 0.1.2 mini-overlap uses a silent Mini text-only tool decision followed by parallel private PCM speech. The 0.1.3 standalone benchmark of 20 synthetic labeled cases x2 resulted in 40/40 successful calls, 90% label agreement, median 214ms, p90 284ms, estimated input spend $0.001657. Four mismatches: twice "Thanks Jarvis, that's all" classified direct rather than sleep; twice private memory question classified direct rather than memory. These errors and context-dependence mean it is not production-ready.

0.1.3 candidate: introduce optional Core-owned read-only shadow classifier on final speech transcripts only; compare with Mini's actual decision, emit route/latency/cost without handing out API keys or control authority. No changes to Realtime audio, lifecycle, PCM gates, tool execution or frontend. No real Luna/tools in current mode.

Risks: transcription may arrive after Mini decision; extra text requests create additional billing and processing; classifier lacks full conversation context; brief sign-offs may close session before shadow finishes; synthetic labels are not correctness or calibrated safety evidence.

Mitigation: opt in via special dev launch mode only; no shadow results are used for action, speech publication or sleep; no unbounded transcripts or persisted input; timeout/fail-closed; keep provider swappable.
