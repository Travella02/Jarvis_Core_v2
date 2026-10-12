# ISSUE 078 — Decisions shadow misclassifies sleep/memory and API speed is not E2E speed

Live 0.1.3 shadow evidence: 8/8 successful, six route agreements, with a disagreement for `Thanks Jarvis that's all` (Mini sleep vs Decisions direct) and different current-data/Luna categorization. Synthetic v1 benchmark: 90% agreement; "That's all" and private-memory prompts misclassified as direct. No observed deterioration in voice quality or PCM pipeline.

**Repair1 experimental work:** precise intent descriptions and contrastive examples; two same-request diagnostic predicates (explicit sleep and private memory); bounded in-memory 1-turn conversational context; answer-name matching and guarded probability parsing; no transcript logging or persistence. Add host logging of arrival order, transcript-ready delay and approximate speech-end-to-Decisions-ready to expose cases where an API call is fast yet too late to control a voice response. Run 30 synthetic cases with 2 repeats.

**Non-negotiables:** Decisions remains shadow-only; no permission changes, sleep authorization, frontend audio changes, Luna/provider execution, or rewriting of the model decision from predicate probabilities. Existing Mini voice and overlap mode untouched. Do not claim classification accuracy before billed live test. Compare results to Mini with end-to-end speech timings; a timing advantage is hypothesis, not established.

**Next gated milestone:** integrate actual Luna via Core with verified result ownership and cancellation in a separate guarded patch only after evaluation of shadow stability. Actions require explicit Core permissions and must not be inferred from Decisions output.
