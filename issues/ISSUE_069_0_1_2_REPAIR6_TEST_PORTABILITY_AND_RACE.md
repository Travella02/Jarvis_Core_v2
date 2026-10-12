# ISSUE 069 — Repair6 test portability and asynchronous scheduling race

**Status:** Automated fix validated; Windows/live verification pending.

The Repair6 focused suite failed on Windows despite the production shadow probe being enabled only by opt-in. Two issues were test-harness bugs: use of OS-default cp1252 to read UTF-8 TypeScript code, and a 15 ms fixed sleep that did not guarantee model-stream completion before probe shutdown. Additional zero-delay waits in cancellation tests could be similarly flaky.

**Fix:** Explicit UTF-8 and deterministic awaits/provider-entry synchronization. No production code changed. Acceptance: focused nine tests and full 536 regression tests pass on Windows; Repair6 shadow-mode live tests remain authoritative for runtime behavior.
