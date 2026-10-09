# Jarvis Core v2 0.1.2-repair4 — Routing Observability + Gate Latency Optimization

Repair4 preserves Repair3's successful pre-speech ownership gate and optimizes only the internal routing transaction around it.

## What changed

### 1. Direct turns no longer copy the request through the router

`route_jarvis_turn` now requires only `route`. The `request` field is required by policy only for Core-owned routes (`reasoning`, `memory`, `action`, `current_data`, `long_task`). `direct` and `sleep` omit it.

That means an ordinary question can produce a tiny internal call such as:

```json
{"route":"direct"}
```

instead of regenerating the user's complete utterance before the real answer can start.

Core-owned routes still fail closed if their request text is missing.

### 2. The silent gate is intentionally lightweight

The desktop's first response now uses:

- router-only instructions;
- forced `route_jarvis_turn` function selection;
- text-only output;
- `reasoning.effort = minimal` for this routing response only;
- a 512-token safety ceiling;
- response metadata marking the stage as `route` and the renderer's turn number.

Normal audible responses keep their existing answer policy. Core/provider authority is unchanged.

### 3. Route ownership is visible in the terminal

The renderer reports its route decision before forwarding the matching function-call event. The Python host prints:

```text
[Jarvis Route] turn=3 | route=direct | owner=realtime | route_ms=... | call_id=...
[Jarvis Direct] turn=3 | realtime-only | call_id=...
```

or, for delegated work:

```text
[Jarvis Route] turn=4 | route=reasoning | owner=core | route_ms=... | call_id=...
[Jarvis Core Call] turn=4 | mode=reasoning | status=started | call_id=...
[Jarvis Core Call] turn=4 | mode=reasoning | status=completed | backend_ms=... | route=... | call_id=...
```

The Electron shell's existing `[Jarvis Core]` prefix still wraps Python stdout. It identifies the host process only; the new inner markers identify actual turn ownership.

### 4. Latency is split at the routing boundary

`[Desktop latency]` now includes:

- `route`;
- `speech_end->route`;
- `route->first_audio`;
- the existing speech-end/response/audio measurements.

This makes future optimization evidence-based instead of guessing where the delay lives.

## V1 lesson carried forward

The included V1 0.3.6 reference repeatedly solved response races by assigning an owner before presentation and correlating later events to that owner. Repair4 follows the same rule. It does **not** use keyword fast paths or weaken the Repair3 pre-speech gate.

## Automated validation

- Focused routing/delegation/desktop policy suite: 55 tests passed.
- Full suite: 521 tests passed, 1 existing skip.
- `python -m core.diagnostics`: `Status: ok`.
- `npm run desktop:check`: passed.

A real Electron/Vite launch remains part of live acceptance because this build environment does not contain the project's `node_modules` tree.
