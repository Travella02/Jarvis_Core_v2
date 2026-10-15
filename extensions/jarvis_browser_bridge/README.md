# Jarvis Core v2 Browser Bridge — Chrome / Edge opt-in alpha

Ported from the read-only v1 0.3.6 Jarvis Browser Bridge. This is an unpacked development extension; browser privileges are substantial. Install only for your own test profile.

1. Open Chrome `chrome://extensions` or Edge `edge://extensions` in your **Windows default browser**.
2. Enable Developer mode; Load unpacked; select this exact folder.
3. Copy extension ID, which is visible on the extension card.
4. Start Jarvis with `JARVIS_BROWSER_BRIDGE_EXTENSION_ID=<copied-id>` in the same PowerShell environment as `realtime_ab.py`.
5. Use the opt-in `mini-overlap-luna-trim-guided-browser-bridge` A/B arm. The extension reconnects after the desktop Core is ready.

The Core side **only authorizes** snapshot, switch/navigation, close tab, back/forward/reload, and verified media play/pause/mute/volume. All other upstream V1 extension features remain inaccessible to v2 Core in this candidate. No permissions on user account credentials or forms have been accepted for this milestone.

This is **not** a production-ready or universal-browser integration. Firefox and other browser adapters are planned later.
