"""Lexical transcript helpers for realtime voice control.

Silero establishes candidate speech presence. Whisper supplies words and ASR
confidence. Repair5e deliberately contains no hard-coded command-word fast path:
speech validation is generic, and accepted text is always interpreted by Jarvis's
normal intelligence/conversation path.
"""

from __future__ import annotations

import re


_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)?")


def lexical_words(text: str) -> tuple[str, ...]:
    return tuple(match.group(0).lower() for match in _WORD_RE.finditer(text))


def has_lexical_speech(text: str) -> bool:
    """Return True when STT produced at least one word/token."""

    return bool(lexical_words(text))


def transcript_compatible(left: str, right: str) -> bool:
    """Return True when rolling STT observations describe the same utterance."""

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
    """Track generic rolling-ASR stability without assigning word semantics."""

    def __init__(self) -> None:
        self._partials: list[str] = []

    @property
    def partial_count(self) -> int:
        return len(self._partials)

    @property
    def has_partial(self) -> bool:
        return bool(self._partials)

    @property
    def partials(self) -> tuple[str, ...]:
        return tuple(self._partials)

    def observe_partial(self, text: str) -> bool:
        normalized = " ".join(lexical_words(text))
        if not normalized:
            return False
        self._partials.append(normalized)
        if len(self._partials) > 8:
            self._partials.pop(0)
        return True

    def stability_score(self, text: str) -> float:
        """Return 0..1 agreement between `text` and prior rolling partials.

        One-word answers are not penalized semantically. If the same short word
        repeats across Whisper snapshots it earns full stability; if a short
        utterance has no partial yet, other confidence signals can still carry it.
        """

        normalized = " ".join(lexical_words(text))
        if not normalized or not self._partials:
            return 0.0

        current_words = lexical_words(normalized)
        compatible = 0
        exact = 0
        for previous in self._partials:
            if transcript_compatible(previous, normalized):
                compatible += 1
            if lexical_words(previous) == current_words:
                exact += 1

        count = len(self._partials)
        compatible_ratio = compatible / count
        exact_ratio = exact / count
        # Exact repeat is stronger evidence, but normal growing partials still
        # receive substantial credit.
        return min(1.0, 0.70 * compatible_ratio + 0.30 * exact_ratio)

    def confirms_final(self, text: str, *, require_partial: bool) -> bool:
        """Legacy helper retained for tests/adapters outside confidence policy."""

        if not has_lexical_speech(text):
            return False
        if not require_partial:
            return True
        return any(transcript_compatible(partial, text) for partial in self._partials)
