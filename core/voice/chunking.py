"""Prosody-safe incremental text chunking for spoken responses.

Core owns chunking semantics so TTS providers remain disposable adapters.
Repair19 keeps sentence-first prosody, but allows one carefully bounded first
clause cut at a comma when it materially reduces time-to-first-audio. The clause
is converted to a complete spoken sentence so local TTS never receives a fake
mid-thought fragment.
"""

from __future__ import annotations


class SpeechTextChunker:
    """Incrementally turn model deltas into natural synthesis utterances.

    Priority:
      1. complete sentence boundaries;
      2. a short, semantically useful first comma-clause only;
      3. strong clause punctuation under size pressure;
      4. whitespace only as a hard safety escape hatch.

    The first comma-clause path is intentionally narrow. It is designed for text
    like ``"Venus rotates extremely slowly, likely because..."`` and not for a
    discourse opener like ``"Well, ..."``. The emitted TTS text becomes
    ``"Venus rotates extremely slowly."`` so the voice model receives a complete
    prosodic unit.
    """

    SENTENCE_ENDERS = ".!?"
    CLAUSE_ENDERS = ";:"

    def __init__(
        self,
        *,
        min_chars: int = 14,
        first_min_chars: int | None = None,
        soft_max_chars: int = 120,
        first_soft_max_chars: int | None = None,
        hard_max_chars: int = 220,
        clause_min_chars: int = 64,
        first_comma_min_chars: int = 18,
        first_comma_max_chars: int = 64,
        first_comma_min_words: int = 3,
    ) -> None:
        if min_chars <= 0:
            raise ValueError("min_chars must be positive")
        resolved_first_min = min(10, min_chars) if first_min_chars is None else first_min_chars
        if resolved_first_min <= 0:
            raise ValueError("first_min_chars must be positive")
        if resolved_first_min > min_chars:
            raise ValueError("first_min_chars must be <= min_chars")
        if soft_max_chars < min_chars:
            raise ValueError("soft_max_chars must be >= min_chars")
        resolved_first = min(96, soft_max_chars) if first_soft_max_chars is None else first_soft_max_chars
        if resolved_first < min_chars:
            raise ValueError("first_soft_max_chars must be >= min_chars")
        if hard_max_chars < soft_max_chars:
            raise ValueError("hard_max_chars must be >= soft_max_chars")
        if clause_min_chars < min_chars:
            raise ValueError("clause_min_chars must be >= min_chars")
        if first_comma_min_chars < min_chars:
            raise ValueError("first_comma_min_chars must be >= min_chars")
        if first_comma_max_chars < first_comma_min_chars:
            raise ValueError("first_comma_max_chars must be >= first_comma_min_chars")
        if first_comma_min_words < 2:
            raise ValueError("first_comma_min_words must be >= 2")
        self.min_chars = min_chars
        self.first_min_chars = resolved_first_min
        self.soft_max_chars = soft_max_chars
        self.first_soft_max_chars = resolved_first
        self.hard_max_chars = hard_max_chars
        self.clause_min_chars = clause_min_chars
        self.first_comma_min_chars = first_comma_min_chars
        self.first_comma_max_chars = first_comma_max_chars
        self.first_comma_min_words = first_comma_min_words
        self._buffer = ""
        self._emitted = 0

    def push(self, delta: str) -> tuple[str, ...]:
        self._buffer += delta
        ready: list[str] = []
        while True:
            decision = self._best_cut()
            if decision is None:
                break
            cut, complete_clause = decision
            chunk = self._buffer[:cut].strip()
            self._buffer = self._buffer[cut:].lstrip()
            if complete_clause and chunk.endswith(","):
                chunk = chunk[:-1].rstrip() + "."
            if chunk:
                ready.append(chunk)
                self._emitted += 1
        return tuple(ready)

    def flush(self) -> str | None:
        text = self._buffer.strip()
        self._buffer = ""
        if text:
            self._emitted += 1
        return text or None

    def _best_cut(self) -> tuple[int, bool] | None:
        active_min = self.first_min_chars if self._emitted == 0 else self.min_chars
        if len(self._buffer.strip()) < active_min:
            return None

        # First response unit only: release a genuinely complete short sentence
        # as soon as it exists. Later chunks retain the original conservative
        # minimum for prosody and continuity.
        for index in range(active_min - 1, len(self._buffer)):
            if self._buffer[index] in self.SENTENCE_ENDERS:
                return index + 1, False

        # Only the first TTS unit may use a comma boundary. Requiring useful
        # length + word count prevents tiny openers such as "Well," or "Sure,"
        # from becoming their own synthetic sentence.
        if self._emitted == 0:
            comma = self._buffer.find(",", self.first_comma_min_chars - 1, self.first_comma_max_chars)
            if comma >= self.first_comma_min_chars - 1:
                candidate = self._buffer[: comma + 1].strip()
                if len(candidate.split()) >= self.first_comma_min_words:
                    return comma + 1, True

        soft_limit = self.first_soft_max_chars if self._emitted == 0 else self.soft_max_chars
        if len(self._buffer) >= soft_limit:
            upper = min(len(self._buffer), self.hard_max_chars)
            for punctuation in self.CLAUSE_ENDERS:
                index = self._buffer.rfind(punctuation, self.clause_min_chars - 1, upper)
                if index >= self.clause_min_chars - 1:
                    return index + 1, False

        if len(self._buffer) >= self.hard_max_chars:
            space = self._buffer.rfind(" ", active_min, self.hard_max_chars + 1)
            return (space + 1 if space >= active_min else self.hard_max_chars), False
        return None
