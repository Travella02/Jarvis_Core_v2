# Jarvis Core v2 0.0.5 Repair5e — Multi-Signal Speech Confidence

Repair5 established the correct ownership split: Silero detects speech presence and Whisper transcribes the utterance. Live testing then exposed one remaining edge case: speech-like nonverbal sounds such as a sneeze or microphone rubbing can legitimately trigger Silero, after which Whisper may hallucinate a short word such as `you`.

Repair5e adds a semantic-free confidence validator between candidate detection and turn ownership.

## Architecture

`Silero candidate -> rolling Whisper -> multi-signal confidence -> accepted/rejected user speech`

The validator combines:
- sustained Silero speech probability;
- Whisper ASR confidence from the same inference request;
- transcript stability across rolling partials;
- utterance duration.

There are no keyword or phrase fast paths. `stop`, `wait`, `yes`, `no`, `why`, names, and arbitrary one-word answers are all scored by the same acoustic/ASR evidence. Once speech is accepted, meaning remains the responsibility of Jarvis intelligence.

## Early interruption vs final turn

Early interruption uses a stricter confidence threshold than final turn acceptance. A first uncertain partial can remain provisional while the microphone continues recording. If stronger evidence arrives, the same utterance can then be promoted to a real interruption.

Defaults:
- final acceptance: 0.58
- early interruption acceptance: 0.68

These values are explicit configuration, not hidden word rules, and should be tuned from live evidence rather than guesswork.

## Whisper confidence

The whisper.cpp adapter requests `verbose_json` and extracts confidence from the same inference call. It prefers word/token probabilities, falls back to average log probability, and can use no-speech probability as supporting evidence. If a provider exposes no ASR confidence, that weight is redistributed across the remaining signals rather than making one-word replies impossible.

Final-only STT providers that emit no rolling partials receive neutral final stability evidence so natural short answers still work.

## Idle behavior

Raw Silero candidates do not reset the 60-second awake timer. Only confidence-confirmed speech counts as user activity. An utterance already in progress receives a short completion grace period at the idle boundary.

## Unchanged

- wake/sleep lifecycle and configurable wake phrases
- GPT-6 Luna model/continuation path
- Qwen whole-response TTS
- Silero as the independent speech-presence detector
- interruption context and heard/unheard accounting
- no semantic command shortcuts in the voice pipeline
