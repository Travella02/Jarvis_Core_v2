# Jarvis Browser Bridge — Chrome / Edge alpha

This opt-in extension is required for **existing-tab reuse**, tab switching and video control in Chrome/Edge. Opening URLs without the extension still uses the system default browser; it cannot guarantee tab reuse. Universal browser support and permission onboarding are not implemented yet.

**Development setup only:** The extension requests powerful tab and site permissions. Install only in your test browser profile. Do not claim it can be installed or enabled without user permission.

1. Open `chrome://extensions` (Chrome) or `edge://extensions` (Edge) in the browser that Windows uses as its default.
2. Enable developer mode, choose **Load unpacked**, and select the `extensions/jarvis_browser_bridge` folder.
3. Note the extension ID shown by the browser and explicitly set `JARVIS_BROWSER_BRIDGE_EXTENSION_ID` in your local Jarvis environment (the ID must match the one displayed).
4. After Repair 3, click **Reload** on the unpacked extension. This is essential: older workers do not understand guarded target navigation and will fall back to default-browser handoffs.
5. Start Jarvis's `mini-overlap-luna-trim-guided-universal-apps` test arm and check `[Jarvis Browser Route]` logs for `reused_connected_tab`.

Jarvis Core independently authorizes operations using same-turn user speech. Browser content is never an action authority. Control is limited to tab navigation/switch/close, back/forward/reload, and verified media play/pause/mute/volume for this candidate; the wider V1 bridge is not exposed. Firefox and other browser adapters are a later milestone.
