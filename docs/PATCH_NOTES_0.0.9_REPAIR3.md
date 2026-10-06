# Jarvis Core v2 0.0.9 Repair3 — WebRTC SDP Framing and Session Diagnostics

## Scope

Repair3 addresses the HTTP 400 returned by OpenAI while creating the first GPT-Live WebRTC session. It changes only the WebRTC session-establishment boundary and browser ICE-completion guard. Jarvis Core, Luna, memory, client delegation, tools, permissions, runtime state, Meridian selection, and the retained WebSocket fallback are unchanged.

## V1 lesson explicitly ported

The read-only V1 reference already had an accepted WebRTC rule: SDP is a byte-oriented line protocol, not arbitrary text. V1 normalized CR/LF variants to CRLF, required a final CRLF, rejected malformed internal blank/control lines, and specifically avoided `.text.strip()`/generic trimming at the provider boundary.

Repair2 accidentally reintroduced that old failure class by calling `.strip()` on the browser SDP offer. Repair3 ports the V1 framing rule directly into the v2 GPT-Live transport.

## What changed

### Canonical SDP framing

`providers/voice_frontend/openai_live/webrtc.py` now canonicalizes both the browser offer and OpenAI answer:

- UTF-8/BOM-safe text handling;
- CRLF line endings;
- required terminal CRLF;
- no internal empty SDP lines;
- no NUL/invalid control characters;
- required `v=0` first SDP line.

### Complete ICE gathering

The browser no longer sends a potentially partial SDP offer after an unconditional 2.5-second timer. It waits for `iceGatheringState === "complete"` and fails locally after 10 seconds if gathering never completes.

### Actionable upstream diagnostics

An OpenAI HTTP rejection now includes the safe response body and `x-request-id` in the local error. The project API key is redacted. If another server-side validation issue remains, the next live run will identify it instead of collapsing to a generic HTTPStatusError.

## Dependencies

None.
