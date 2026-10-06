# 0.1.0 Repair3 — Desktop Orb State Transition Polish

Repair3 is a presentation-only polish pass for the Desktop Alpha particle orb.

## Changes

- Keeps one persistent particle field alive across every Jarvis state.
- Blends state parameters with exponential easing instead of hard visual swaps.
- Gives each state its own motion/color identity:
  - ready: calm blue/violet drift,
  - listening: cyan focus/expansion,
  - thinking: faster violet swirl,
  - speaking: brighter icy-blue energy with an intentionally tiny scale pulse,
  - working: faster teal stream,
  - connecting/error: softened/dimmed states.
- Reduces speaking scale motion to less than half a percent so Jarvis feels alive without visibly bouncing.
- Leaves Realtime 2.1 Mini, Cedar, WebRTC, semantic VAD, Core delegation, caption pacing, and latency telemetry unchanged.

## Architecture boundary

The renderer remains presentation-only. Repair3 does not change model selection, provider routing, Core authority, runtime APIs, Realtime session behavior, or backend intelligence.
