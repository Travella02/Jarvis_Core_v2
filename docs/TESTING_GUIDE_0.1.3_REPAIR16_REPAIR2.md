# Repair16 Repair2 — Installation & live acceptance

### Apply
Close Jarvis, extract the Repair2 ZIP directly into the Jarvis_Core_v2 root, and from the activated virtualenv run:

```powershell
python .\apply_0_1_3_repair16_repair2.py
```

### Automated checks (one command at a time)

```powershell
python -m unittest tests.unit.test_0_1_3_repair16_repair2_native_cue_budget -v
```

```powershell
python -m unittest discover -s tests -v
```

```powershell
python -m core.diagnostics
```

```powershell
npm run desktop:check
```

```powershell
npm run desktop:build
```

### Test the notification **before** using Luna
Close Jarvis first. Run this local-only sound test; it does **not** call AI APIs:

```powershell
python -m apps.desktop_cancel_cue
```

Expected: a clear two-note ding in the Windows **default playback device**; terminal says `cue_status=playback_api_completed`. That terminal message means Windows playback succeeded at the API level but cannot prove that the headphones were audible. If no sound, verify Windows default output selection, volume/mute and application mixer before making another API call.

### Live Luna cancellation test (8 seconds **after** the sound)

```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim-cancel-test
```

Wake: `Hey Jarvis`. Ask:

> Jarvis, compare three production architectures for a multi-tenant AI assistant, including authorization, tenant isolation, retries, and audit logging. Recommend the best architecture and explain why.

At the native two-note cue (not by watching the terminal), say immediately:

> Actually, forget that. What's nine times eight?

Expected: Jarvis responds `72` and never speaks the previous Core answer. The terminal should report `phase=stale_result_discarded` and `phase=test_summary | outcome=PASS`. If the timer expires, it should report `NOT_TESTED`, never a false PASS.

Repeat the delegation. After the ding, say:

> That's all, Jarvis.

Expected: immediate sleep, no stale Core response, and a PASS cancellation summary. If the model chooses not to delegate the complex request, that does not validate the cancellation hold.

### Normal mode regression

```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim
```

Ask a complex architecture question to trigger Core. Expect `[Jarvis Luna Budget] output_limit=1024` and completed, genuinely useful speech. Also ask `What's nine times eight?` and verify the fast natural direct response has no cue.

**Five standard wake/sleep phrases** (test them sequentially in normal mode):

1. `Hey Jarvis, what planet is called the Red Planet?` — wake, answer Mars without an extra greeting.
2. `Go to sleep, Jarvis.` — sleep silently.
3. `Jarvis, what's seventeen times six?` — wake, answer 102.
4. `Thanks, Jarvis.` — acknowledge naturally and stay awake.
5. `Thanks Jarvis, that's all.` — sleep silently.

Do not remove patch files, installer or `.patch_backups` and do not commit until live testing is accepted.
