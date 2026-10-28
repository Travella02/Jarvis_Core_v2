# Jarvis Core v2 — 0.1.5.9 Repair1 — Mini Routing & Joined-Word STT

**Exact baseline:** user-supplied Jarvis_0.0.0_clean_checkpoint(2).zip (file name is not authoritative for version). No reset or force overwrite.

- Desktop Realtime Mini's active overlap-decision guidance now explicitly classifies numbered YouTube video-result requests as `browser_action(select_result, site=current, value=spoken ordinal)` instead of direct chat or `play` on the current video. The existing Core authorization remains authoritative and the extension still must verify search results; selecting a watch URL is not a guarantee of autoplay.
- Adds fullscreen/exit-fullscreen guidance in the same specific mode.
- A bounded STT normalization in Core handles transcripts like `Jervis OpenYouTube` as `Jervis Open YouTube` **only after** Mini proposed a browser operation. It is *not* a keyword router or an alternate authorization channel. Negations, hypotheticals, compound requests, destination mismatches and missing search topics still fail closed.
- No audio/wake/sleep provider changes, API billing changes, forced file overwrites or unrelated version bumps.

**Caveat:** A client-side prompt fix improves the probability of the model choosing the correct tool but cannot guarantee correct speech-to-tool behavior. Windows live testing of model selections, browser extension, and page navigation is required before acceptance.

**Version metadata:** This uploaded source includes 0.1.5.9 code/docs/tests while root VERSION, RELEASE_MANIFEST.json, README and package.json still reference 0.1.3. This Repair1 intentionally does not make an unrelated metadata migration. Track separately before publishing.

**Release gate:** run focused suite, unit regression, desktop build and Windows live tests from the testing guide. Do not cleanup or commit until the live acceptance passes.
