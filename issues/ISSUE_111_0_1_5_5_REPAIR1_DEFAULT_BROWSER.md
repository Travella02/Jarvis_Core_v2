# ISSUE 111 — 0.1.5.5 Candidate1 default browser navigation regression

Observed on Windows: after navigating/closing tabs in Candidate1, `Open YouTube` returned `browser_failure`, while short questions and other tab commands often continued to work. Candidate1 bypassed the OS default browser for navigation, forcing a separate Playwright Chromium/Edge profile. User needs normal requests to use the system default across browser vendors.

Repair1 separates Core-verified `open`/`search` handoffs to the OS from explicit Jarvis-managed browser automation (`open_managed`). Does not claim universal control of external browsers. Preserves spoken failure reporting and safety checks.

Additional security regression test: unapproved fully-qualified host must not be accepted by matching a short site label.

Status: automated tests pass; Windows live acceptance pending. Future scope: cross-browser automation via per-browser extension or user-consented native bridge, with capability and session evidence.
