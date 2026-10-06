# ISSUE-049 — Desktop captions outran speech, placeholder avatar lacked identity, and WebSocket scopes reached StaticFiles

## Observed

The first 0.1.0 Desktop Alpha successfully opened a native Jarvis window and carried a Realtime Mini + Cedar conversation, but three presentation/runtime problems were visible during live testing:

1. output transcript text appeared much faster than Cedar spoke it;
2. the initial ring/orbit placeholder did not visually communicate the desired living Jarvis identity;
3. the terminal emitted Starlette `StaticFiles` `assert scope["type"] == "http"` tracebacks from WebSocket traffic.

The user also perceived slower responses than the prior browser lab, but 0.1.0 had not intentionally changed the Realtime model, Cedar, WebRTC, or semantic VAD settings.

## Cause

- Realtime transcript deltas were appended directly to React state on arrival, even though transcript generation can run ahead of audio playout.
- The avatar was intentionally a minimal first placeholder.
- Mounting `StaticFiles` at `/` created an HTTP-only catch-all ASGI application capable of receiving unmatched WebSocket scopes.
- No desktop timing telemetry existed to distinguish endpointing delay from model or playout delay.

## Repair

0.1.0 Repair1 adds a paced transcript queue, a code-native flowing particle orb, GET-only SPA/static routes, and per-turn latency telemetry. It intentionally leaves Realtime Mini, Cedar, WebRTC, Core delegation, and VAD behavior unchanged until measured desktop timings justify a change.
