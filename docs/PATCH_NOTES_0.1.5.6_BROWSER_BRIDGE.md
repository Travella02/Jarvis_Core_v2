# 0.1.5.6 Candidate 1 — Existing Browser Bridge (opt-in)

**Baseline:** user-supplied `Jarvis_current_clean_checkpoint.zip` (October 15, 2026). Not yet a release or committed milestone.

## V1 comparison and origin

Reviewed read-only `Reference_jarvis_corev1/Jarvis_0.3.6_clean_checkpoint.zip`:
- `jarvis/browser/bridge.py` — Core-owned websocket commands, request/result IDs, timeouts, reconnect state.
- `extensions/jarvis_browser_bridge/{manifest.json,service_worker.js,content.js}` — installed extension for existing Chrome/Edge tabs, navigation, structural DOM operations, HTML5 and YouTube media, retries, verification.
- V1 issues `ISSUE_280` and `ISSUE_300`: recover from extension/Core restarts and validate WebSocket runtime prerequisites.

Ported the bridge transport + extension **as isolated code**, retaining V2's separate transcript authorization, Core action gateway, realtime Mini selection and provider independence. V1 runtime/permissions/provider modules are *not* imported into V2.

## What changes

- New opt-in `mini-overlap-luna-trim-guided-browser-bridge` A/B mode; legacy semantic, managed-browser and media profiles remain unchanged.
- The extension installed in Chrome or Edge connects to v2's loopback desktop host, only when explicitly paired with its extension ID.
- Existing one-to-one matching same-site tab may be selected and navigated for open/search, including searches on YouTube and Google. Ambiguous matches open a new tab via the OS default instead.
- No connection or no matching tab: `open`/`search` hand off via Windows default browser as before. No hidden Chromium profile is launched in this mode.
- Connected extension allows Core-verified select tab, close named/current tab, next tab, back/forward/reload, and media play/pause/mute/unmute/absolute volume. Browser confirms state; a mere accepted request is not success.
- Initial tab discovery uses a metadata-only `tabs_list` operation rather than reading webpage content. Content scripts are injected on demand for authorized media controls; Core cannot call the original V1 arbitrary DOM operations.
- Failed/unsupported operations return a Core failure for natural audible reporting; visually successful operations remain silent.
- V2 bridge has a strict Core operation allowlist: page click/type/submit/scripting/download/etc. are deliberately **not exposed in Candidate 1** even though the upstream V1 extension implements more.
- Direct Mini audio has no extra model call and remains on its preexisting fast path.

## Boundaries — candid limitations

- **Chrome/Edge initial alpha only:** a connected extension is required for real tab/media control. Firefox, Brave, Opera and other browsers are *planned adapters*, not claimed supported. OS default URL opening works without an extension, but does not permit controlling tabs.
- An extension connected in a browser that is not the OS default is *not automatically the default browser*. For initial testing, install and pair only the extension in the Windows default browser.
- This candidate does **not** yet select/click the first search result, play arbitrary video by title, fill forms, browse page links, fullscreen, or control desktop tabs across multiple different browsers simultaneously.
- MV3 extension requests site access. It is an alpha development install, not a store-signed production package. Do not enable on sensitive profiles or accounts until browser-permission review and security hardening are complete.
- Extension origin pairing is a local development safeguard, not a full authenticated public distribution design. A malicious local process may spoof WebSocket headers; public release will need stronger pairing and process-level hardening.
- When Core is cancelled after sending a browser command, the browser might finish the command. Never claim that cancellation undoes an external side effect. This remains a required robustness test before production use.

## Source-level invariants

1. Core validates independent same-turn speech evidence before any browser effect.
2. Only one result per turn, with replay/deduplication and existing cancellation behavior.
3. Background/sleep does not close the user's browser.
4. Reusing an existing tab verifies returned URL; fresh OS opens only verify OS handoff.
5. No extra Mini or Luna inference just to identify a browser target.
6. V1 reference archive remains unmodified.
