# ISSUE 085 — Windows cp1252 debug log crashes control WebSocket on Unicode speech

Status: Repair7 candidate — live acceptance pending.

## Reproduction

On Python 3.11 Windows with stdout configured as `cp1252`, a user or model
transcript containing the character `我` (`U+6211`) reached `desktop_user`
logging. `json.dumps(..., ensure_ascii=False)` preserved the character; the
subsequent `print` raised `UnicodeEncodeError` before the host could process
that speech. The unhandled exception escaped `DesktopRealtimeSession.open_control`
into `/ws/control`, destroying the WebSocket and making the desktop appear
OFFLINE. This is distinct from Repair6's output-token truncation recovery.

## Repair7

* Render the debug chat string as readable Unicode when stdout supports it;
  otherwise escape unsupported characters using JSON `\uXXXX` escapes,
  leaving the original speech text and Core delegation untouched.
* Set stdout/stderr print error handling to `backslashreplace` when the desktop
  host starts, protecting other provider, status and error logs from triggering
  the same crash. Preserve terminal encoding and do not mutate project .env,
  locale, or user-supplied content.
* No changes to voice PCM, Realtime, token budgets, Decisions API, sleep/wake,
  Luna execution, cancellation or personality.

## Live verification

1. Run focused/full regression, diagnostics and desktop checks on Windows.
2. Start `mini-overlap-luna-cancel-test`, reproduce a long Mini truncation,
   confirm `phase=recoverable_incomplete` and READY (not OFFLINE).
3. Speak or type a message including `我`, or another non-cp1252 character.
   The host must log safely and the control session must stay connected.
4. Ask a basic follow-up and verify the answer. Continue Luna hold/cancel
   testing only once the control socket remains stable.

Keep all patch files and backups until live acceptance; do not commit yet.
