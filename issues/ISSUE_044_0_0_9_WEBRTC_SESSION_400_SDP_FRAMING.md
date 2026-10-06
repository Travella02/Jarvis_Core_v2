# ISSUE 044 — GPT-Live WebRTC session creation returns HTTP 400

## Observed

The 0.0.9 Repair2 browser lab reached the trusted Python broker, then OpenAI rejected `POST /v1/live/sessions` with HTTP 400 before a WebRTC session was created.

## Root-cause risk identified

Repair2 called `.strip()` on the browser SDP offer before sending it to OpenAI. That removes terminal CRLF framing. The V1 reference project had already solved this class of WebRTC problem by canonicalizing SDP to CRLF and requiring a final CRLF; it explicitly warned against stripping SDP as generic text.

Repair2 also allowed its ICE-gathering wait to succeed after 2.5 seconds even when the browser had not reached `iceGatheringState === "complete"`. OpenAI's current GPT-Live WebRTC connection sequence requires the client to wait for ICE gathering and then send the completed local SDP offer.

The upstream 400 body was not preserved, so the first failed run could not distinguish malformed SDP from another request-validation failure.

## Repair

0.0.9 Repair3:

- ports the accepted V1 SDP canonicalization contract into the v2 GPT-Live WebRTC adapter;
- preserves CRLF line framing and a terminal CRLF for offers and answers;
- rejects malformed blank/control-character SDP locally;
- waits for browser ICE gathering to actually complete or fails locally after a bounded timeout rather than sending a knowingly partial offer;
- preserves the safe OpenAI error body and request ID when session creation is rejected.

No Jarvis Core, Luna, memory, delegation, tool, permission, or voice-provider authority changes are included.
