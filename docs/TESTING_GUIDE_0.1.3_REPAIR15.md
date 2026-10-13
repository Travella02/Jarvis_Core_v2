# 0.1.3 Repair15 — Windows live voice acceptance

### Automated checks (separate commands)

```powershell
python -m unittest tests.unit.test_0_1_3_repair15_wake_ack -v
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

### Live configuration

Launch with **accepted Repair13 PCM trim**, not rejected Repair14 compact router:

```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim
```

### Focused wake-only checks

1. While sleeping, say **`Jarvis.`** *and then be quiet*. Jarvis should wake and answer briefly (natural Mini speech, no canned WAV). Look for `[USER SPEECH] source=wake_transcript | text="Jarvis."` and `[JARVIS REPLY]` from the same turn.
2. Say **`That's all, Jarvis.`** to sleep. Then **`Hey Jarvis.`** without a question; Jarvis should wake and acknowledge briefly, ideally with a little variation.
3. Sleep, then **`Hey Jarvis, what is seventeen times six?`** He must answer **102** without an extra welcome or unnecessary separate voice turn.
4. Sleep, then **`Jarvis, what planet is known as the Red Planet?`** He must answer Mars directly.
5. Sleep, then say something without the wake phrase (e.g. `Hello computer`). No Realtime conversation should start.

### Five standard regression phrases
Use these in sequence while monitoring the logs:

1. **`Hey Jarvis, what planet is called the Red Planet?`** — wakes and answers Mars.
2. **`Go to sleep, Jarvis.`** — sleeps silently.
3. **`Jarvis, what's seventeen times six?`** — wakes and answers 102.
4. **`Thanks, Jarvis.`** — ordinary gratitude while awake, not sleep.
5. **`Thanks Jarvis, that's all.`** — sleeps silently. If STT differs, capture exact transcript and `sleep_evidence_mismatch` evidence.

### Audio checks
Test rapid wake-only → next question, barge-in during greeting, spoken feedback with 1–5 words, and full 60-second idle-sleep (if feasible). Listen for clipped greetings, crackling, popping, double/overlapping replies. Check that the first words of commands are not cut off and regular direct answers remain responsive. If something fails, keep patch files and backups.

### Report
Send terminal screenshots/logs (especially `wake_detected`, `USER SPEECH`, `JARVIS REPLY`, `route`, `first_audio_ms`), plus whether wake-only acknowledgments sound human and whether any wake+command caused a double response. These wake-start numbers **must not** be compared directly to the already-awake Repair13 first-audio median.
