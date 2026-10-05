# ISSUE 038 — 0.0.7 dependency resolver conflict

The initial 0.0.7 candidate pinned `websockets==16.0` while
`openai[realtime]==3.13.0` requires `websockets>=13,<16`.

This prevents a clean dependency install even though the runtime code itself is
compatible with the 15.x client API used by the diagnostic.

Repair1 pins `websockets==15.0.1`, which also satisfies Uvicorn's
`websockets>=10.4` standard extra.
