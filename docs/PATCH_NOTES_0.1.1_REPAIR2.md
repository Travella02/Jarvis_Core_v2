# Jarvis Core v2 0.1.1 Repair2 — Adaptive Conversational Brevity

## Why this repair exists

0.1.1 Repair1 fixed silent sleep correctly, but live acceptance showed that Realtime Mini still treated a short continuation such as **“Why does that happen?”** like an invitation to deliver a paragraph. The prior “one to three sentences” guidance was too permissive.

## What changes

Only the provider-neutral Jarvis conversational instruction supplied to the OpenAI Realtime frontend is tightened:

- ordinary conversational answers default to one or two short spoken sentences,
- short continuation questions answer only the missing point rather than restarting the explanation,
- unnecessary background, second analogies, recaps, and unsolicited related facts are discouraged,
- personality, warmth, humor, curiosity, and spontaneous reactions remain explicitly welcome,
- explicit requests for detail/depth/examples override the short default and may expand naturally.

The word ranges are behavioral targets, not hard truncation limits. Jarvis must finish a coherent thought.

## What does not change

- Realtime 2.1 Mini remains the default conversational frontend.
- Cedar, WebRTC, wake detection, sleep lifecycle, Core delegation, permissions, memory boundaries, idle sleep, and desktop presentation are unchanged.
- No output-token hard cap is introduced because hard clipping would damage natural speech and detailed-answer requests.
