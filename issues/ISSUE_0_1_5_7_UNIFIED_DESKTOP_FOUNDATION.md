# 0.1.5.7 — Separate web navigation from installed app actions

**Problem:** The earlier Mini tool definition treated nearly every 'open' request as a website/browsing intent. Users should be able to ask naturally for websites, apps, games and files without always saying 'browser', while app execution remains independently authorized by Core.

**First fix:** Add a new typed `launch_app` tool to the already proven Mini decision turn, leaving `browser_action` and its extension behavior unchanged. Give Core a small audited catalog of trusted Windows system apps. Require matching trusted same-turn speech, reject hypotheticals/negations/compound actions, keep idempotency, and report failures truthfully.

**Reference:** V1 ISSUE-256/258/260: prefer exact known routes and do not confuse launch handoff with visible verification; avoid discovery on voice critical path.

**Not addressed yet:** arbitrary installed app discovery, unknown-app permission onboarding, file/folder targeting, app closing, monitoring window visibility, general GUI control, different browser profiles/extension installers. These are separate scope with separate tests.
