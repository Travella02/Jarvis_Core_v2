# 0.1.5.8 Repair 2 — Single-route Windows handoffs and repeated discovery order

- **Observed:** On Oct 20, user's `Open Discord` was rejected (`unverified_user_intent`), and other apps returned handoff without verified window. Prior Repair 1 used exactly one selected OS route per launch.
- **Issue:** When a valid authorized launch route returns false or throws, alternative OS-registered routes for the *same installed app* are ignored; a working route is not remembered for future sessions.
- **Repair:** Core-first authorization, bounded same-identity route retries, persistent local preference / attempt history, stale cache validation against actual OS-discovered routes, stopped retries on handoff acceptance.
- **Tests:** Inert tests exercise failure/exception/fallback, preferred-route reuse and invalidation, corrupt/tampered caches, no unsafe escalation, replay idempotence and accepted-handoff duplicate prevention. No audio changes.
- **Caveat:** This does NOT bypass or fix `unverified_user_intent`; diagnose independently with confirmed transcript/model proposed target. Live Windows user verification pending.
