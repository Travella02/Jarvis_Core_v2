# ISSUE 050 — 0.1.0 desktop dust orb and character captions

## Observation
Repair1 proved that the code-native particle avatar and paced captions were viable, but live acceptance showed two presentation problems: the particle field still read as points *inside* an orb rather than the particles *being* the orb, and transcript pacing still revealed whole words/chunks rather than feeling synchronized to Cedar speech. Delta-boundary formatting could also produce display text such as `enough!Glad`.

## Repair2 decision
Keep the accepted Realtime Mini + Cedar + WebRTC + Core delegation path unchanged. Increase particle density and canvas scale so the dust field itself defines a larger spherical presence. Replace token pacing with audio-gated, character-by-character caption reveal and a display-only spacing normalizer.

## Non-goals
No VAD changes, model changes, prompt/personality changes, backend routing changes, memory changes, or new desktop features.
