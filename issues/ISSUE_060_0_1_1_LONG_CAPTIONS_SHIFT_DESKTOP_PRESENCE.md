# ISSUE 060 — 0.1.1 Long captions shift the desktop Jarvis presence

## Symptom

Detailed responses expanded the caption element vertically, moving the orb and eventually pushing content beyond the application viewport.

## Fix

The compact caption surface is now fixed-height and bottom-anchored. It auto-scrolls to the newest text, fades older overflow at the top, and exposes a full-response overlay when the compact surface overflows.

## Product rule

Response length must never change the geometry of Jarvis's primary presence. Long-form reading is a secondary surface layered over the presence, not a reason to reflow it.
