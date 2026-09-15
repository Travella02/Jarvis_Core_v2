# V1 Reference Inventory

## Canonical fallback

- Reference archive: `Reference_jarvis_corev1/Jarvis_0.3.6_clean_checkpoint.zip`
- Embedded `VERSION`: `0.3.6`
- Final repair-equivalent content present: **Repair17 — Blocked Action Preflight & Error Fidelity**
- Repair17 evidence in archive:
  - `docs/PATCH_NOTES_0.3.6-repair17.md`
  - `docs/TESTING_GUIDE_0.3.6-repair17.md`
  - `issues/ISSUE_342_BLOCKED_ACTION_PREFLIGHT_AND_ERROR_FIDELITY.md`
  - `tests/test_blocked_action_preflight.py`
- New v2 master handoff records 0.3.6 as accepted/committed after the final Repair17 regression pass on **September 10, 2026**.
- The supplied clean archive intentionally contains no `.git`, so a historical Git commit hash cannot be independently recovered from this artifact.
- The embedded V1 `RELEASE_MANIFEST.json` still identifies the Repair17 package as a live-acceptance candidate. The newer v2 master handoff is the canonical later record of final acceptance.

## Reference policy

The V1 archive is read-only. Do not extract its source over v2, import V1 modules as the v2 runtime, copy its environment, or silently preserve legacy provider/runtime coupling.

Use V1 as a behavior oracle where behavior was accepted, a regression-test source, a UX/permission semantics reference, and a source of isolated implementation lessons after reviewing whether they fit v2 boundaries.

## High-value behavior/reference areas

The supplied archive contains substantial reference coverage for:

- Permissions/security and blocked-action preflight
- Browser/computer actions
- Gmail and Calendar behavior
- Account/auth/billing/entitlement foundations
- Memory and speaker/voice behavior
- Realtime interruption and voice pipeline repair history
- Provider gateways and cloud-service boundaries
- Large historical issues/docs/test inventory

## Known migration lesson

V1 accumulated provider/realtime/text/speech concerns across legacy gateways and app layers. V2 must preserve proven behavior without recreating that coupling. In particular, tool authority, conversation truth, intelligence routing, and realtime voice orchestration need independent contracts.

## V1 behavior to explicitly benchmark later

As the corresponding v2 milestones arrive, build behavioral/regression checks for:

- Wake/sleep and natural wake phrasing
- Interruption/barge-in and heard/unheard response handling
- Active referent handling such as “pause it” / “resume it”
- Permission persistence: Allow once / Always allow / Block
- Natural confirmations and preflight blocking before consequential execution
- Gmail, Calendar, Browser, and Computer action semantics
- Multi-speaker identity behavior and voice enrollment quality rules
- Account/billing entitlement enforcement and fraud resistance

This document records reference targets only. It does not make those systems part of 0.0.1.
