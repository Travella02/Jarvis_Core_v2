# Issue: follow-up site search creates new tab; tab selection focus race

**Observed:** `Open YouTube` then `Search YouTube for Sidemen` opened a second tab during 0.1.5.8 Repair 2 live checks. Core was using OS default browser handoff when no connected, authorized extension was available. OS URL launch does not provide reliable tab identity. Existing bridge navigation also used `tab_switch` followed by active-tab navigation; another focus change could lead to the wrong tab receiving the URL.

**Repair:** target a fresh verified site-tab ID atomically, guard the pre-navigation host in the extension, and use same-session affinity only after verified navigation. Add route diagnostics and explicit protocol capabilities. Leave default-browser fallback for disconnected/missing/old extension, without falsely claiming reuse.

**Acceptance:** no wrong-site hijack, no duplicate retries, unchanged fast conversational turns, no arbitrary app/web mixup. An authorized connected extension reuses a matching YouTube tab across follow-up searches. Without one, report fallback. User must confirm Windows live result.

**Future:** browser permission onboarding + broader adapters (beyond current Chromium alpha), without silent installation or elevated permissions.
