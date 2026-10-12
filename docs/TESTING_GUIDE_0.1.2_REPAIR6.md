# Repair6 Phase 1 — Safe parallel probe live tests

Do not commit or clean temporary patch artifacts until live acceptance. Copy/paste terminal commands individually.

1. Unzip `Jarvis_Core_v2_0.1.2_repair6_patch.zip` into the Jarvis project root (do not replace `.env`).
2. `python .\apply_0_1_2_repair6_patch.py`
3. `python -m unittest tests.unit.test_0_1_2_repair6_parallel_shadow -v` — expected 9 passing.
4. `python -m unittest discover -s tests -v` — expected 536 tests total, 1 existing skip.
5. `python -m core.diagnostics` — expected `Status: ok`.
6. `npm run desktop:check`
7. For the optional parallel experiment, append or set `JARVIS_PARALLEL_SHADOW_PROBE=1` in your own local `.env` and ensure `JARVIS_DESKTOP_CONVERSATION_TRACE=1` (accepted transcript events are needed). Do not share `.env`.
8. `npm run desktop`.

Say, one at a time:

- `Jarvis, what planet is known as the Red Planet?` — expected single direct "Mars" answer; route `direct`; optional shadow metrics but NO shadow audio/text in UI.
- `Jarvis, use your Core to explain why idempotency matters when a client reconnects to a runtime.` — expected single real Core result; route `reasoning`; no filler or fake preamble.
- `Jarvis, start a background task that builds a project while I'm gone.` — expected truthful Core `long_task` unavailable; NO shadow action execution.
- `That's all, Jarvis.` — expected normal sleep and no stray audio.

Send terminal log sections containing `[USER SPEECH]`, `[Jarvis Parallel]`, `[Jarvis Route]`, `[Jarvis Core Call]`, `[JARVIS REPLY]`, `[Desktop latency]`. Observe whether `[Jarvis Parallel] ... transcript_after_route` appears; if frequent, transcript-based speculative Core cannot meaningfully overlap the gate and we should adjust design.

**Important:** This intentionally DOES NOT yield faster audio in phase 1. It tests whether concurrency is viable without leaking speech. Phase 2 can attempt isolated PCM buffering only after we validate the timeline and costs.
