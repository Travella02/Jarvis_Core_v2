# Jarvis 0.1.5.5 — Browser Media + Named Tabs + Phonetic Wake (Candidate 1)

**Status:** experimental; not committed or accepted. Patch from accepted 0.1.5.4 Repair1.

## Changes

- New separate A/B mode: `mini-overlap-luna-trim-guided-browser-media`.
- Existing `mini-overlap-luna-trim-guided-managed-browser` remains unmodified in capability and wake matching.
- Core-authorized `select_tab` and `close_named_tab` by explicit host, without acting on a guessed tab. If more than one matching tab exists the action fails, rather than choosing arbitrarily.
- Current visible HTML5-video controls: play, pause, mute, unmute, and **absolute** volume 0–100%, with independent transcript validation. Relative volume commands are intentionally unsupported in this slice.
- Wake listening can tolerate `Jervis` and `Dervis` transcription variants of the default Jarvis name in the new mode. The heuristic is conservative and **text-based**, not an acoustic phoneme model or calibrated recognition confidence. Custom wake words remain exact. Does not change interruption/VAD while awake.
- Action outcomes remain Core-owned. Visible successful actions require no speech, unsuccessful/unsupported actions receive truthful failure feedback.

## Non-goals / limitations

- Does not select video search results, click arbitrary elements, seek, fullscreen, type into fields, control protected DRM players, or automate account operations.
- Browser controls a Jarvis-managed isolated visible browser, not pre-existing Edge/Chrome tabs.
- HTML5 video must be discoverable in the top-level page; nested cross-origin iframe players may not work. Browser may disallow scripted `play()` until a user gesture.
- Only a single recognized requested action per turn is currently executed; compound instructions requiring two tool actions fail closed.
- This is an alpha test candidate. Do not clean or commit before unit/build/live acceptance.

## Dependencies

Playwright (`requirements-browser.txt`) and Chromium/Edge, previously installed in 0.1.5.4. No new packages required.
