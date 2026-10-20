# Windows app discovery: duplicate Discord registrations and missing Spotify

Observed from 0.1.5.8 candidate Windows screenshots Oct 15, 2026:
- Discord launch refused `app_ambiguous` due to multiple discovered routes.
- Spotify launch refused `app_not_found`, despite known installation.

Root causes visible in code: identical display names from different .lnk paths were treated as distinct ambiguous apps. Windows app enumeration did not include Get-StartApps / OS packaged identities.

Repair candidate: same-app route consolidation, Start-app enumeration/launch, read-only diagnostics. Must verify on actual Windows device. Preserve previous 0.1.5.7 and conversation paths.
