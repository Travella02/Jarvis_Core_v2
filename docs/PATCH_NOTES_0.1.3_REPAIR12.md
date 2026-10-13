# 0.1.3 Repair12 — Decisions/Core-Luna paired latency instrumentation

- Opt-in `mini-overlap-luna-decisions-shadow` launcher: original real Core/Luna configuration plus Decisions shadow. No production route changes.
- Shadow emits one bounded `[Jarvis Repair12 A/B]` metric per observed turn with first audio, Mini route, estimated Decisions readiness, potential router headroom, agreement, and authority declaration. No transcript in metric.
- Offline `scripts/repair12_latency_report.py` summarizes latency and accuracy from two local PowerShell logs without cloud calls.
- Focused unit tests protect Core authority, API failure handling, route disagreements, timing and baseline launcher parity.
- Preserves all Repair11 PCM reuse, Realtime audio, verified sleep and Core/Luna behavior. No editing personality in this repair.
- Windows live approval pending. Keep apply script, patch files and backups until passed; cleanup and commit only after approval.
