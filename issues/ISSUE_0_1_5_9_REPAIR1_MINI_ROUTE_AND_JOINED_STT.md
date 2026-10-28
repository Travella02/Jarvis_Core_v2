# 0.1.5.9 Repair1 — Mini direct-route result selection / joined STT

**Windows live observation:** five conversational tests passed. First YouTube open failed then succeeded; Sidemen search succeeded; “Play the first video” did not navigate. Mini emitted `tool=none`/`phase=direct` even though existing 0.1.5.9 Core supports verified `select_result`. Separately `Jervis OpenYouTube` failed Core's word-boundary intent evidence. Original Repair1 ZIP refused to install because its `App.tsx` SHA-256 baseline did not match the user's current checkpoint; installer changed nothing.

**Repair:** target exact uploaded source. Update Mini's authoritative desktop instruction to use select_result for numbered YouTube results, and normalize only joined verb+site STT boundary in Core. Preserve all independent authorization checks, query/topic verification, and no-playback-claim discipline.

**Acceptance:** focused/unit/build + live Windows voice + same-tab navigation; otherwise continue repair iteration. This is not accepted or committed yet.
