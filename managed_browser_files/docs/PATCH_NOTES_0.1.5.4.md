# 0.1.5.4 — Managed Browser Foundation (opt-in alpha)

## Goal
Start real browser automation without touching the accepted fast Mini/Luna voice, VAD, sleep or audio pipelines. Existing `mini-overlap-luna-trim-guided-semantic` remains the known-good control mode.

## This focused slice
- New explicit mode `mini-overlap-luna-trim-guided-managed-browser` uses the existing **single** Mini routing/tool decision and Core-authorized tool result path. No extra model routing call on ordinary conversation.
- Visible, isolated Playwright Chromium/Edge browser with an ORVEX-specific local profile. Never controls or reads personal default-browser tabs. Profile persists while Jarvis sleeps and is closed at application shutdown.
- Open ordinary public HTTPS site homepages by natural language: e.g. Google, Wikipedia, GitHub, NASA; follow explicit spoken hostnames too. Model proposes a domain, not arbitrary executable URLs, and Core independently checks that the same website is mentioned in the **committed current-turn transcript**.
- YouTube/Google search results pages when requested; navigation back/forward/reload, switch between Jarvis-managed tabs, close current managed tab.
- Core rejects private/local/special destinations, arbitrary ports, IP addresses, URL paths in model arguments, malformed hostnames, Unicode lookalike domains, negation, compound privileged requests, stale turns and missing/invalid independent user-turn evidence. No form filling, downloads, script execution or untrusted webpage instructions as actions.
- New-turn cancellation and stale-result suppression: managed browser work does not block the control WebSocket. A cancelled navigation could already have begun; no automatic retry or false claim of reversal.
- Visible successful browser actions remain silent. Unavailable/failed/denied actions return a truthful spoken explanation via the existing repair1 Core result voice path.
- Optional Playwright dependency loaded only on first managed-browser action. Separate `requirements-browser.txt`; other modes are unchanged.

## Known limitations / non-goals
- Opening a *homepage* is not arbitrary deep-link navigation. No page reading, clicks, playback controls, filling forms, checkout, arbitrary file/device access or control of Chrome/Edge tabs that Jarvis did not open. Planned follow-up milestones.
- Browser navigation `commit` is **not** verification of fully loaded page content; some websites may block automation, redirect, require sign-in, or fail even if the browser reached the page. This alpha supports only public hostnames that Core can bind to the user utterance.
- Browser startup may take several seconds on first use; the **managed mode only** has a longer action-result watchdog. Ordinary direct-question latency path is untouched; live Windows measurements required.
- Programmatic unit tests run with a mock browser and do **not** establish Windows browser or microphone behavior.
- The repository's `VERSION` / package metadata pre-date 0.1.4 in the accepted baseline. This patch does not silently rewrite unrelated release metadata; reconcile deliberately in a later bounded milestone.

## Changes and tests
- Added `core/tools/managed_browser.py`, `apps/desktop_managed_browser.py`, optional dependency list, new opt-in A/B mode, simulated safety regressions.
- Modified the Core desktop action integration and renderer watchdog/prompt conditional only for the experimental browser mode, and updated one previous watchdog contract assertion to allow the new opt-in timeout while preserving its legacy five seconds.
- Do **not** clean or commit until the Windows live testing sequence passes and the project owner accepts it.
