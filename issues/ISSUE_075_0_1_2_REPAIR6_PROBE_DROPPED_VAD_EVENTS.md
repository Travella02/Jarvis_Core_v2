# ISSUE 075 — Tool selection probe ignores all user turns

Reproduction: `mini-tools`, speak normally; STT emits transcript but no response. Terminal shows `turn=n/a`, session turns=0.

Root cause: the probe-only early return prevented VAD `speech_started` and `speech_stopped` reaching the existing handler; manual response creation only happens in that handler.

Repair: bypass probe interception for the two lifecycle events; retain text-only response/tool interception and safe simulated tool results. Requires live Windows acceptance.
