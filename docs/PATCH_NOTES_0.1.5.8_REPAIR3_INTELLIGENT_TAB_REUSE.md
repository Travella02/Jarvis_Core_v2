# 0.1.5.8 Repair 3 — Conservative, verified tab reuse

**Baseline:** Repair 2 commit (app fallback + local launch history). This is an incremental patch, not a replacement checkpoint.

## Purpose

- Restore the desired `Open YouTube` → `Search YouTube for Sidemen` behavior **when the authorized browser bridge is connected**. If the target exists, navigate that same tab, not an arbitrary current tab.
- Fix a TOCTOU focus race: the old extension's `navigate` operation applied to whichever tab became active between selecting and navigating. The new protocol names the intended `tab_id` and requires the tab's pre-navigation host to still match `expected_host`. This prevents an unrelated tab from being hijacked.
- Handle two tabs on one site safely: active matching tab wins, otherwise previously verified tab affinity (same extension instance) wins; otherwise fail closed to default-browser handoff rather than choosing one randomly. Affinity is ephemeral, not stored in disk history or user memory.
- Add `navigation_route` diagnostics (`reused_connected_tab`, `default_bridge_disconnected`, `default_extension_outdated`, `default_ambiguous_tabs`, etc.). These logs include no page titles, query contents, or URL strings.
- Declare `navigate_target_guarded` as a required extension capability. If an old browser worker remains installed, do not send the new protocol to it.

## Boundaries

- **A browser connection remains necessary** for existing-tab management. ShellExecute/default-browser URL handoffs cannot reliably select existing tabs across arbitrary installed browsers. Without a connected extension, URLs still open using the OS default, usually in a new tab.
- Updating an unpacked extension requires the browser to reload it. Do **not** install browser extensions silently or claim that a webpage granted browser permissions. Chrome/Edge alpha only; not Firefox, Safari, etc.
- Do not change app discovery, launch history, speech input, wake/sleep, normal voice response routing, or semantic action authorization.
- Respect explicit website vs app distinction. No new text-to-command fast paths were added.
- If the bridge command returns an uncertain result, never retry by opening another tab.

## Files

- `core/tools/default_browser_bridge.py`: target selection, protected navigation and route logging state
- `core/tools/managed_browser.py`: action-route diagnostic (only on browser tool operations)
- `extensions/jarvis_browser_bridge/service_worker.js`: atomic tab-id/host-guarded navigation
- `extensions/jarvis_browser_bridge/manifest.json`: extension version bump
- `tests/unit/test_0_1_5_6_browser_bridge.py`, `tests/unit/test_0_1_5_6_browser_bridge_search_repair2.py`: updated fake bridge capabilities
- `tests/unit/test_0_1_5_8_repair3_tab_reuse.py`: new offline safety and regression coverage

## Forward plan

For public launch, implement explicit browser permission/onboarding with clear connected/disconnected status, and browser-specific adapters. This patch intentionally does **not** implement unattended universal cross-browser tab control.
