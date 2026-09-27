# Jarvis Core v2 0.0.4 Repair27 — Fast First Speech Chunk

Repair26 showed that the physical playback path is already fast. The next
deterministic opportunity is the delay between Luna's first text delta and
the first complete speech unit sent to resident Qwen.

## Changes
- Voice turns ask Luna to begin with one direct, complete 3-6 word sentence
  and place the sentence-ending punctuation immediately after it.
- Filler openers such as "Sure" and "Of course" are discouraged.
- Only the first speech unit may release a complete sentence at a 10-character
  floor instead of the normal 14-character floor.
- The first useful comma-clause threshold moves from 24 chars / 4 words to
  18 chars / 3 words.
- Later chunks keep the existing conservative behavior.

## Deliberately unchanged
Whisper, Luna transport/service tier/reasoning, resident Qwen streaming,
Repair25's 250 ms startup runway, and Repair26's low-latency PortAudio path.

## Acceptance
We want `Luna first text -> first speech chunk` to fall without making Jarvis
sound fragmentary, repetitive, or robotic. Naturalness wins over a tiny raw
latency improvement.
