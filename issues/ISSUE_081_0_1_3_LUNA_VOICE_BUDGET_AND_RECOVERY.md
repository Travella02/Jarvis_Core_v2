# ISSUE 081 — Core Luna voice response truncated and desktop marked OFFLINE

## Live observation (0.1.3 Repair2 + Repair3)
Core Luna completed a 1325-character answer after 5719ms, but its new out-of-band
Realtime Mini speech response hit the 1024 shared output token budget. The voice
response returned `incomplete: max_output_tokens`, `candidate_incomplete` was
raised, and the desktop `error` state displayed `Jarvis is offline`, even though
no provider disconnect was confirmed.

## Repair4 scope
* Only the `core_luna_voice` synthesis request uses the documented `inf` token
  budget; original speculative candidate and decision limits stay unchanged.
  The Core result remains bounded to 3000 text characters by the existing path.
* Keep the Core-verified text for the active turn. If Core voice generation fails
  or is incomplete, stop the audio gate, display that verified text, and leave
  the already-awake session operable. Do not claim that fallback text was spoken.
* Avoid displaying an incomplete Core voice transcript as a finished answer.
* Emit `Jarvis Luna Voice` completion/fallback markers in terminal logs.
* No changes to Realtime identity/voice, Core reasoning, Luna routing,
  decisions-shadow, permissions, wake/sleep, or default response length.

## Caveats and acceptance
* A partial audio prefix may already have played if a late incomplete status
  arrives during streaming; the fallback is clearly logged and retains the
  full verified text. Large outputs still depend on provider behavior.
* Run focused/full tests and desktop checks, then live-test Core handoff, direct
  conversation, dry-run actions, wake/sleep, interruption and no stuck offline.
* Preserve patch backup, do not commit until live approval.
