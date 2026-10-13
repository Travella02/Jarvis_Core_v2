# Jarvis 0.1.3 Repair16 Diagnostic1 — Core/Luna failure cause

**Purpose:** A live Core/Luna delegation returned `status=failed` but lacked actionable and safe failure evidence in the console. This is a diagnostic-only follow-up to installed, uncommitted Repair16.

Changed: `apps/desktop_luna.py` adds `phase=core_failed` with whitelisted safe status/HTTP code/provider error class/error code/parameter and presence booleans. `providers/intelligence/openai/provider.py` enriches safe exception categories with validated status/code/parameter only. **No raw error messages, stack traces, API keys, HTTP response bodies, user input, or model output are added to logging.**

Unchanged: Mini routing, wake-only acknowledgments, leading-silence PCM trim, Core permissions, dry-run actions, cancellation, and Luna voice rendering. This patch **does not attempt to repair the cause** until the live logs reveal it.

See `docs/TESTING_GUIDE_0.1.3_REPAIR16_DIAGNOSTIC1.md`. Do not clean/commit while Repair16 delegation remains unaccepted.
