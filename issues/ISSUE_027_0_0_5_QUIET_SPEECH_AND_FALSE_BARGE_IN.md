# ISSUE 027 — 0.0.5 quiet speech rejection and false barge-in

## Observed

During live 0.0.5 Repair2 testing:
- normal user speech was repeatedly logged as `insufficient-energy`,
  `peak-below-threshold`, or `speech-span-too-short`;
- a valid `Why is that?` transcript was captured;
- Luna generated a response, but the turn was marked interrupted before any
  Qwen audio was queued (`queued=0`, `heard=[none]`).

## Root cause

Two different concepts were conflated:
1. acoustic activity used to locate candidate audio;
2. semantic proof that the user actually spoke words.

Repair2 used sustained fused activity as the interruption trigger and the
pre-STT evidence gate still used RMS/peak as hard rejection criteria.

## Resolution

Repair3 makes local STT lexical output authoritative:
- RMS/peak no longer reject quiet candidates before STT;
- non-lexical final STT output is ignored;
- early active-turn interruption uses a bounded local-STT lexical probe;
- final lexical capture can still preempt the active response if the early probe
  does not fire;
- raw onset/activity no longer cancels a response.

Status: fixed in 0.0.5 Repair3 candidate; requires live acceptance.
