"""Lexical speech validation for realtime voice control.

0.0.5 Repair5 separates two jobs that Whisper must not own simultaneously:
Silero VAD is the independent authority that human speech exists; Whisper only
decides what that already-confirmed speech said. These helpers validate text and
retain conservative partial-transcript telemetry, but transcript text can no
longer create a user turn from silence by itself.
"""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)?")
_EARLY_SINGLE_WORDS = frozenset(
    {
        "actually",
        "cancel",
        "hold",
        "jarvis",
        "no",
        "pause",
        "stop",
        "wait",
        "why",
    }
)
_EARLY_HALLUCINATION_PHRASES = frozenset(
    {
        "thank you",
        "thanks for watching",
        "you",
    }
)


def lexical_words(text: str) -> tuple[str, ...]:
    return tuple(match.group(0).lower() for match in _WORD_RE.finditer(text))


def has_lexical_speech(text: str) -> bool:
    """Return True when STT produced at least one real word/token."""
    return bool(lexical_words(text))


def transcript_compatible(left: str, right: str) -> bool:
    """Return True when two rolling STT observations describe the same utterance.

    Whisper partials normally grow from a prefix into the final sentence. We
    intentionally compare words rather than punctuation/case so the transcript
    stream can confirm a real turn without using microphone amplitude as proof.
    """

    a = lexical_words(left)
    b = lexical_words(right)
    if not a or not b:
        return False
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if tuple(longer[: len(shorter)]) == tuple(shorter):
        return True
    if min(len(a), len(b)) <= 2:
        return a == b
    common = len(set(a) & set(b))
    return common / min(len(a), len(b)) >= 0.67


class TranscriptEvidenceTracker:
    """Confirm a speech turn from Whisper partial/final agreement.

    Used after independent neural speech-presence confirmation. Partial/final
    compatibility remains useful for diagnostics and text stability, but this
    tracker is no longer the authority for whether speech physically occurred.
    """

    def __init__(self) -> None:
        self._partials: list[str] = []

    @property
    def partial_count(self) -> int:
        return len(self._partials)

    @property
    def has_partial(self) -> bool:
        return bool(self._partials)

    def observe_partial(self, text: str) -> bool:
        normalized = " ".join(lexical_words(text))
        if not normalized:
            return False
        self._partials.append(normalized)
        if len(self._partials) > 6:
            self._partials.pop(0)
        return True

    def confirms_early_partial(self, text: str) -> bool:
        """Return True when a rolling partial is strong enough for barge-in.

        V1 could trust one provider transcription delta. Local Whisper rolling
        inference is more prone to silence hallucinations, so Core v2 is stricter:
        deliberate one-word controls/follow-ups may commit immediately; arbitrary
        phrases need agreement with an earlier partial from the same STT stream.
        """

        normalized = " ".join(lexical_words(text))
        if not normalized or normalized in _EARLY_HALLUCINATION_PHRASES:
            return False
        words = tuple(normalized.split())
        if len(words) == 1 and words[0] in _EARLY_SINGLE_WORDS:
            return True
        if len(self._partials) < 2:
            return False
        current = self._partials[-1]
        return any(
            transcript_compatible(previous, current)
            for previous in self._partials[:-1]
        )

    def confirms_final(self, text: str, *, require_partial: bool) -> bool:
        if not has_lexical_speech(text):
            return False
        if not require_partial:
            return True
        return any(transcript_compatible(partial, text) for partial in self._partials)


def confirms_early_interruption(text: str) -> bool:
    """Conservative early-barge-in confirmation.

    A rolling STT probe may run before the user finishes the utterance. To
    avoid cancelling Jarvis on common silence hallucinations, require either
    two lexical words or one deliberate control/follow-up word.
    """

    normalized = " ".join(lexical_words(text))
    if not normalized or normalized in _EARLY_HALLUCINATION_PHRASES:
        return False
    words = tuple(normalized.split())
    if len(words) >= 2:
        return True
    return words[0] in _EARLY_SINGLE_WORDS
