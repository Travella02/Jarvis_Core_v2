# 0.1.1 Repair6 — Silent Sleep Priority + Stable Transcript Surface

## Scope

This repair fixes two live-acceptance regressions without changing the accepted Realtime Mini + Cedar + WebRTC architecture.

1. **Explicit sleep after Repair5 manual response creation**
   - Repair5 attached response-specific compact instructions to every manually created response.
   - Those turn instructions did not restate the lifecycle/tool priority strongly enough, and Realtime Mini could speak a sign-off instead of calling `sleep_jarvis`.
   - The per-turn policy now places lifecycle/tool control above spoken formatting and explicitly requires `sleep_jarvis` as the initial and only output for clear sleep intent.

2. **Long transcript text moving the Jarvis presence**
   - The caption block previously grew with the response, pushing the orb and composer around during detailed answers.
   - Captions now live in a fixed-height viewport. New text stays anchored at the bottom, older lines fade at the top, and the orb never moves because a response is long.
   - When the response exceeds the compact viewport, an expand control opens a full-screen overlay for the complete currently displayed response. Escape or the close button returns to Jarvis without affecting the voice session.

## Non-changes

- Realtime model remains `gpt-realtime-2.1-mini`.
- Cedar, WebRTC, Semantic VAD, manual response creation, Core delegation, local wake, and 60-second idle sleep are unchanged.
- Normal and expanded safety ceilings remain 1024 / 2048 tokens.
- The repair does not add a client-side semantic keyword fast path for arbitrary conversation. Sleep continues through the existing Realtime lifecycle tool contract.
