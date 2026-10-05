# Jarvis Core v2 0.0.7 Repair1 — Realtime/WebSocket dependency compatibility

## Symptom

`python -m pip install -r requirements.txt` fails with `ResolutionImpossible`.

## Cause

The 0.0.7 candidate pinned `websockets==16.0`, while
`openai[realtime]==3.13.0` requires `websockets>=13,<16`.

Uvicorn 0.48.0 only requires `websockets>=10.4`, so `websockets==15.0.1`
satisfies both the OpenAI Realtime SDK and the local Jarvis runtime API client.

## Fix

Pin `websockets==15.0.1` consistently in:
- `requirements.txt`
- `pyproject.toml`
- the foundation dependency contract test

No Jarvis runtime, voice, intelligence, reconnect, state, API, or protocol behavior
is changed by this repair.
