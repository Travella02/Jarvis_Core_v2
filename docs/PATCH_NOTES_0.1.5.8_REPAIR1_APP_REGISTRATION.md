# 0.1.5.8 Repair 1 — Duplicate app identities + Windows Start apps

Problem observed in Windows live testing:
- Installed Discord returned `app_ambiguous` despite user asking for the ordinary Discord app.
- Installed Spotify returned `app_not_found` despite being installed.

Changes:
- Collapse identical displayed application identities across separate Windows launch registrations. Route priority favors current-user Start Menu shortcuts, then other shell-approved registrations. Distinct branded variants (Discord Canary, etc.) retain their distinct names. Does not arbitrarily launch an unrelated app.
- Include Windows Get-StartApps registration in the background inventory, covering many Microsoft Store/UWP/MSIX installations that are absent from App Paths or .lnk shortcuts.
- Launch OS-discovered Start identities through Windows Explorer's AppsFolder handoff, no arbitrary model-supplied commands or paths.
- Generic product-name descriptor trimming (e.g. Spotify Music -> Spotify) with ambiguity guard if more than one app would share an alias.
- Read-only `scripts/app_inventory_probe.py` to diagnose missing registrations without leaking full app paths to transcripts.

Non-goals: recursively scanning user disks, arbitrary .exe running, file search, closing apps, alias personalization, side effects without same-turn Core verification, pretending that a launched window was seen. Spotify needs validation on this user's actual Windows installation; Get-StartApps may still omit some unpackaged/portable apps.

Do not commit until accepted in live Windows test, including original five fast speech queries and browser regressions.
