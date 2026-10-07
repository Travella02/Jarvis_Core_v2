# ISSUE 062 — Inline Transcript Scroll Ownership

## Symptom

Repair6 kept long transcript text inside a stable fixed-height region, but users could not reread earlier lines inline because the viewport was hidden-scroll and automatically forced to the newest content on every caption update.

## Cause

Streaming output and reader viewport state shared one ownership rule: every incoming character was treated as permission to move the scroll position.

## Repair

The inline caption now owns an internal scrollbar. It follows new content only while the reader is near the bottom. Scrolling upward transfers ownership to the user until they return near the latest text. The fixed frame and full-screen reader remain unchanged.

## V1 reference lesson

V1 already solved the same class of bug in its conversation transcript with a near-bottom threshold and explicit separation between streaming transport state and user viewport state. Repair7 ports that principle into the minimal v2 caption surface.
