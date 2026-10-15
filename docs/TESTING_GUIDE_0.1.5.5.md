# Jarvis 0.1.5.5 Candidate1 Testing Guide

Stop Jarvis and extract patch ZIP into repo root. Do not clean or commit before live acceptance.

```powershell
python .\apply_0_1_5_5_browser_media_wake.py
```

```powershell
python -m unittest tests.unit.test_0_1_5_5_browser_media_wake -v
```

```powershell
python -m unittest discover -s tests -q
```

```powershell
npm run desktop:build
```

```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-browser-media
```

## Five standard regression checks

1. `Hey Jarvis, what planet is called the Red Planet?` → Mars, one utterance.
2. `Go to sleep, Jarvis.` → sleeps, no unnecessary reply.
3. `Jarvis, what's seventeen times six?` → 102.
4. `Thanks, Jarvis.` → stays awake and acknowledges naturally.
5. `Thanks Jarvis, that's all.` → sleeps silently.

## New wake tests while sleeping

1. `Hey Jervis` → wakes.
2. `Hey Dervis, what's seventeen times six?` → wakes and answers 102 in same turn.
3. `Jervis, open Google` → opens managed Google tab.
4. `The service was nervous` → should **not** wake.
5. `I said Jervis yesterday` → should **not** wake.

Check the terminal wake transcript spelling and whether the app entered awake. If it did not wake, report the actual transcript.

## Tab tests

1. `Open Google` then `Now open Wikipedia` (two tabs).
2. `Switch to Google` → focuses Google tab.
3. `Close Wikipedia` → closes Wikipedia, not Google.
4. `Do not close Google` → no action.
5. `Close Google and Wikipedia` → no partial action; should decline compound request.
6. `Close Google` when two Google tabs are open → should fail rather than guess.

## Media tests

Manually open a video page in the managed browser and **start a visible HTML5 video** once. Do not expect Jarvis to click the search result yet.

1. `Pause the video` → pauses.
2. `Play the video` → resumes, if site permits scripting.
3. `Mute the video` → muted.
4. `Unmute the video` → unmuted.
5. `Set the volume to 30%` → player level becomes 30%.
6. `Do not pause the video` → no action.
7. `Increase volume by 30%` → currently unsupported; no action.
8. After media, ask `What's 17 times 23?` → 391 with speed comparable to accepted mode.

Watch for visible action verification, no false claims, and expected Core failed results for unsupported pages. Report audio behavior and any unexpected wake or false wake. Cleanup/commit only after accepted test results.
