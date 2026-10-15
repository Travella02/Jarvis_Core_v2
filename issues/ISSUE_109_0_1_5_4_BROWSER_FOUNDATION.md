# ISSUE 109 — Managed Browser Foundation

Status: candidate / awaiting Windows acceptance.

User request: Free natural-language browser use, expanding beyond the approved YouTube-only opener. Must not hardcode spoken phrases or sacrifice normal conversation latency. Need a credible basis for tab, playback, and later full automation.

Root limitation in 0.1.5.3: `SemanticBrowserGateway` owns an exact approved YouTube hostname and delegates only OS `webbrowser.open_new_tab`; it cannot control an open tab or verify browser navigation.

Change: opt-in Playwright-managed browser separate from default user browser and existing tested action mode; Core checks current-turn user evidence, destination and typed operation; navigation/tab methods share a provider-agnostic browser operations interface.

Deferred: page inspection/clicking, video controls, authenticated workflows, user review/approval UI for ambiguous hosts or deep links, mature browser permission model, production installer bundling, website compatibility, multi-user account boundary, and independent security review.

Risks: persistent browser profile stores cookies; webpage could navigate to malicious content even when initial homepage is allowed; opening a browser may take seconds; cancellations may race already-started navigation. Never ingest webpage instructions as user commands. Tested programmatically with mocked adapter only; Windows acceptance is outstanding.
