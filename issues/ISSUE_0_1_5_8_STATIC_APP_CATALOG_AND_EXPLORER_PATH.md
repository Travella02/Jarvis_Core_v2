# 0.1.5.8 — Static app catalog and wrong File Explorer path

Observed live 0.1.5.7: File Explorer returned app_launch_unavailable and Discord opened a website instead of local app. The previous three-item enum was a temporary safety prototype, not a scalable installed-app system. Its `GetSystemDirectoryW` lookup was inappropriate for explorer.exe, which commonly lives in the Windows directory.

Candidate 0.1.5.8 adds bounded, background Windows Start Menu / App Paths discovery, Core name resolution, and corrected explorer.exe path. It preserves independent turn authorization and does not accept model-provided command lines. Existing stable 0.1.5.7 tool schema is kept available for A/B. Actual Windows acceptance pending.
