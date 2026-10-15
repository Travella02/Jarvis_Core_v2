# Jarvis Core v2 — 0.1.5.2: Opt-in Natural Language Browser Actions

**Baseline:** accepted 0.1.5.1 checkpoint (applied to accepted 0.1.4 voice checkpoint). Live acceptance PENDING. Do not commit until accepted.

## Focus
- New launch arm: `python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-actions`.
- Realtime Mini still selects the existing silent `test_action` tool. The desktop does not run the model's arguments.
- In this arm only, a single `test_action` selection can request Core's approved browser gateway **after** a same-turn verified typed text or committed Realtime audio-item transcript arrives.
- Core independently checks the exact 'open YouTube' command; one hardcoded allowlisted URL only. No arbitrary URLs, apps, file access, shell commands, or autonomous background work.
- The Core result is returned to the renderer and spoken via the existing private Core-result speech pathway. The browser-open API success means the OS accepted the request, **not** that the webpage finished loading.
- Late transcripts, duplicate selection events, mismatched item bindings, stale/superseded turns, missing or unsupported commands do not execute.
- Existing `mini-overlap-luna-trim-guided` arm remains disabled for real tools and unchanged in tool routing.
- Test-only native/browser notification cues are silenced in A/B launches (`JARVIS_SILENT_TEST_CUES=1`); ordinary Jarvis voice is unaffected. The standalone cue utility remains manually available without this flag.

## Known limits
- Only YouTube is approved. 'Open Google' MUST NOT open a page in this milestone.
- This is an opt-in local-desktop alpha, **not** complete user-account/device permission infrastructure. Independent transcript authorization protects against model-supplied tool arguments, but does not authenticate arbitrary callers able to forge localhost UI-control events. Harden loopback origin/auth before general release.
- Model may occasionally fail to choose `test_action`; that is a routing failure, not authorization to open a browser anyway.
- Current WebRTC transcription is provider-produced and can mishear; for real-world actions requiring higher trust, add user confirmation and stronger identity checks in later milestones.
- Real end-to-end microphone/OS integration MUST be accepted on Windows before this patch is committed.
- A longer action-result response might still be interrupted by existing false-barge-in limitations; this patch does not modify VAD.
