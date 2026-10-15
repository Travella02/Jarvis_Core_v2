# Jarvis Core v2 0.1.5.5 Candidate1 Repair1 — Default Browser Navigation

Status: Windows live acceptance pending. Never commit or clean patch/backup until user accepts.

## Diagnosed regression

0.1.5.5 Candidate1 replaced normal website opening with Playwright persistent-profile navigation. After tab churn the managed browser could fail to relaunch/reuse its context and returned `browser_failure`. It also broke the OS-default-browser expectation.

## Focused repair

- In the 0.1.5.5 browser-media experiment only, ordinary `open` and `search` use a Core-authorized, asynchronously dispatched **OS-default-browser** handoff (Windows `os.startfile`). They no longer start or depend upon Playwright. OS acceptance is not page-load verification.
- Requests for other public sites remain domain-bound to independently confirmed transcripts. Unsafe/suspicious/ambiguous URLs and compound commands remain denied; explicit invalid hosts no longer fall back to a familiar site label.
- A separate, explicit `open_managed` command can open a site in Jarvis's Playwright browser for its existing tab/media functions. If the user asks for the managed browser, Core refuses to silently choose the default instead.
- Named tabs and HTML5 media control **only** work in the separate Jarvis-managed browser. This patch does not enable controlling arbitrary tabs/videos in the user's default browser; that will require extension/native integration or another permitted automation bridge.
- The previously accepted managed browser mode, stable action mode, voice, wake handling and PCM pipeline remain unchanged. No additional classification model calls.
- Existing failures continue to speak; successful visible site opening needs no spoken acknowledgment.

## Verification

- Full Python unit suite: 868, skipped 1, OK (Linux/container mocks; no real Windows browser opened).
- New tests: OS-default handoff, managed-browser failure isolation, exact safety binding, explicit opt-in, negative cases and idempotency.
- Windows Electron/Vite build and Windows live tests remain mandatory.
