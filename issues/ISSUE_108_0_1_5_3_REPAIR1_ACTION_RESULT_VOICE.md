# ISSUE 108 — Browser actions silently lose Core acknowledgment

**Symptoms:** Successful YouTube launches logged `status=completed` in Core, while desktop logged `status=unknown reason=result_timeout` ~5s later. Google/other blocked actions also timed out and did not speak.

**Root cause:** `BrowserRealtimeRelay.notify_desktop` filters on `kind == core_luna_result` and silently discards `kind == core_tool_result`.

**Repair:** Explicitly allow `core_tool_result`; same-turn UI ownership guard retained; successes silent; verified failures spoken via existing Realtime audio result reader; missing acknowledgment described as unconfirmed, not failed. No new permissions.

**Verify:** Both unit relay delivery and Windows live audio. No commit before user acceptance.
