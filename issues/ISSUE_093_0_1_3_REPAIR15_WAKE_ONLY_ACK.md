# ISSUE 093 — Wake-only commands produce no audible acknowledgment

**Observed:** Local wake detection of `Jarvis` / `Hey Jarvis` with `command_present=False` transitions desktop presence to awake but does not dispatch a user turn, and Realtime remains `Ready` without answering.

**Cause:** `DesktopWakeService.listen()` forwards only `command_text` to the desktop. `startRealtimeSession()` skips `dispatchTextToRealtime` if that command is empty.

**Repair15:** Send confirmed wake-only local transcript in an optional websocket field, dispatch it once after Realtime connects, and use a turn-specific short acknowledgment instruction for speculative Mini audio. Routing permission and PCM gating unchanged. Wake+command remains no greeting.

**Validation:** focused host websocket and wake-phrase tests; 740-test suite 1 skipped; Core diagnostics. Windows desktop build/live tests pending; this issue is **not closed** until user acceptance.
