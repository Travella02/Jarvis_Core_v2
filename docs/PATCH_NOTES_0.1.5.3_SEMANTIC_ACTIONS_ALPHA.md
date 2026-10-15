# Jarvis Core v2 — 0.1.5.3 Semantic Actions Alpha

**Experimental, opt-in only. Not a checkpoint.** Requires the exact 0.1.5.2 Repair2 baseline. The accepted `mini-overlap-luna-trim-guided` arm is unchanged; the previous `...guided-actions` experiment remains available as a comparison.

## Purpose

Replace the old full-sentence `re.fullmatch()` command grammar and hardcoded `youtube` tool target with a provider-independent, **typed tool proposal**. The existing Mini decision chooses whether to answer, delegate to Luna, sleep, or propose `browser_action(site='youtube', intent='open'|'search', query?)`. Core—not Mini—validates current-turn evidence, supported destination, argument schema, denial/negation/conditional safeguards, and one-action-per-turn behavior. No arbitrary URLs, shell access, email access, or other websites are enabled. Search URLs are built exclusively by Core on youtube.com from encoded search text. A successful visible browser launch should not trigger a spoken confirmation.

## Design and performance boundaries

- No new classifier/model request is added to normal conversation. This uses the existing out-of-band Mini decision and speculative PCM candidate, leaving VAD, AEC, wake, sleep, audio capture, voice output, and Luna invocation untouched.
- The new model tool schema is present **only** in the new experimental launcher; no change in normal baseline. Because added metadata and model variance can still affect latency, Windows A/B measurements are mandatory before acceptance.
- Core's conservative safety veto is **not** semantic understanding. It rejects suspicious/uncertain requests. The goal is model-native intent recognition *without a full-sentence command whitelist*, not a promise that every wording works today.
- Browser-launch accepted is **not** equivalent to page loaded or search quality verified.
- Deictic searches such as "find a video about that" are still experimental: the out-of-band decision may lack reliable earlier conversation context. Never treat a guessed query as established conversation memory. Confirm the real query in the browser during live testing; if wrong, log an issue instead of claiming success.
- This is local single-user prototype security. An authenticated, per-user permissions boundary and consent flow are prerequisites to a public release.

## Files

- `core/tools/semantic_browser.py`: whitelist-owned Core validation, encoded search and replay protection
- `apps/desktop_semantic_actions.py`: independent same-turn evidence, model proposal parsing, cancellation of stale actions
- `apps/desktop_alpha.py`: opt-in typed-tool advertisement and Core action dispatch
- `apps/desktop/ui/src/App.tsx`: pass structured proposed tool args while preserving verified current-turn input and existing PCM routing
- `scripts/realtime_ab.py`: dedicated `mini-overlap-luna-trim-guided-semantic` A/B launcher
- `tests/unit/test_0_1_5_3_semantic_actions.py`: natural wording, security, replay, search, latency-path structural tests

No API keys are inserted and no dependencies are added.

## Acceptance gate

Pass focused tests, full suite, diagnostics, desktop check + build; then compare **20 matched direct conversational turns**, sampled alternately between guided and guided-semantic modes. Include wake and sleep checks, strong variation in natural action language, negative/conditional requests, YouTube search results, and a mid-action interruption test. Record speech-end-to-first-audio p50/p95 for *direct* requests separately from action latency. Do not commit until direct conversation latency and live speech quality remain acceptable and every safety check passes.
