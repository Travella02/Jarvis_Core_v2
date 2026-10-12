# ISSUE 079 — 0.1.3 Repair2: real Core Luna reasoning through Realtime Mini voice

## Baseline

0.1.3 Repair1 (Decisions refinement) is a live-tested, shadow-only comparison. Realtime Mini remains the sole owner of overlap audio routing. The 0.1.2 PCM/wake/sleep fixes are the accepted baseline.

## Change

Introduce **opt-in `mini-overlap-luna`** mode. When Mini selects `ask_luna` in its silent turn-bound decision, the renderer aborts the private speculative response without releasing speech and sends **selection only** to Core. Core uses the confirmed user transcript (never free-form tool arguments) and its existing `DelegationOrchestrator`/`ConversationCore.submit_delegated()` to route reasoning to a real OpenAI IntelligenceProvider. A matching, still-current Core result is handed back to Realtime for a separate, tool-disabled, out-of-band natural voice response. Old turns are dropped when speech interrupts, new turns begin, or the session sleeps. Unverified work is never reported as complete. Real computer actions and background jobs remain **disabled** in this mode.

This is not an automatic switch to Decisions as routing authority; Decisions stays shadow-only in its separate mode. Normal `mini-overlap` stays the 0.1.2 fallback.

## Acceptance criteria

1. Default, original overlap, and Decisions shadow modes remain unchanged.
2. Real reasoning request: logged `[Jarvis Luna] phase=selection` followed by `phase=result | status=completed`, and a single natural voiced Core answer. **No dry-run placeholder**.
3. Ordinary conversation: direct Realtime Mini reply, **no** Core Luna call.
4. Computer action: blocked dry-run, no execution or false claim.
5. Interrupted Core reasoning: old result never speaks and does not contaminate the following turn.
6. Failed provider/absent transcript: truthful failure, no success claim.
7. Sleep during pending delegation: session closes and local wake listener returns; no late Luna audio.
8. Clean PCM, matching caption, natural voice tone; user must confirm live.
9. Keep patch files/backups until automated and live acceptance; then clean and commit.

## Limits

This opt-in prototype incurs additional backend Luna billing. Session-level spoken continuity is not yet a persistent Core+Realtime shared memory. Follow-up voice delivery uses a separate Realtime response after Luna's result, so complex responses take longer than direct Mini answers. Electron/WebRTC live behavior and server billing remain to be validated on the target Windows machine.
