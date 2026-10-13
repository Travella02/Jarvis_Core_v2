# 0.1.3 Repair15 — Wake-only voice acknowledgment

## Objective
When the *local* sleeping listener confirms an utterance containing only a wake phrase (e.g. `Jarvis`, `Hey Jarvis`), Jarvis should acknowledge that he is awake using GPT-Realtime-2.1 Mini's usual audio output rather than silently waiting for a follow-up command.

## Changes
- `apps/desktop_alpha.py`: attach `wake_only_transcript` **only** when local wake detection succeeds and its parsed `command_text` is empty. This preserves exact recognized punctuation/wording from Whisper.
- `App.tsx`: on wake-only, create one user Realtime text turn from the verified local transcript. Wake+command is unchanged: dispatch only the remaining command and do not greet first.
- Mark *this turn* as wake-only; normal speculative Mini audio gets a 1–5-word natural-acknowledgment instruction. Mini generates speech; no prerecorded response or hardcoded greeting.
- Silent classifier still decides direct vs Core/Luna; the normal PCM gate still waits for Core's direct authorization. Nothing skips sleep checks, permission checks, or voice validation.
- No changes to Repair13 leading-silence PCM trim, routine Mini routing, wake matching/phonetics, or TTS.
- The local wake transcript is also available through normal `desktop_user` development tracing as `source=wake_transcript`; the visual caption remains Jarvis's answer to keep the current interface minimal.

## Limitations / safety
- Wake startup includes local endpointing, connection setup and Realtime initialization: **not** measured by Repair13's already-awake 655ms latency benchmark.
- Mini may occasionally say more than five words; live tests must check brief natural output, audible first phoneme, and no extra greeting when a command is present.
- Already known `Jervis` transcription misses remain outside scope (phonetic matching later).
- Repair14 compact router was rejected; this patch is built on the accepted Repair13 source and does **not** reintroduce compact routing.
- No real external actions are enabled.

## Release workflow
Extract ZIP into the project root; run `python .\apply_0_1_3_repair15_patch.py`; validate; obtain live user acceptance; then clean temporary patch artifacts/backups and commit. Do not overwrite unknown local changes.
