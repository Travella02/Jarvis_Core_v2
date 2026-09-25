"""Provider-neutral normalization from display text to spoken text."""

from __future__ import annotations

import re

_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\((?:[^)]+)\)")
_MARKDOWN_IMAGE = re.compile(r"!\[([^\]]*)\]\((?:[^)]+)\)")
_HEADING_OR_BULLET = re.compile(r"(?m)^\s{0,3}(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)")
_MULTI_SPACE = re.compile(r"[ \t]+")
_MULTI_NEWLINE = re.compile(r"\s*\n\s*")


def normalize_speech_text(text: str) -> str:
    """Return text suitable for TTS without changing display/transcript text.

    This intentionally focuses on deterministic presentation artifacts rather
    than semantic rewriting. Dates, money, URLs, abbreviations, and richer
    verbalization can grow behind this same Core-owned boundary later.
    """

    value = text.strip()
    if not value:
        return ""
    value = _MARKDOWN_IMAGE.sub(lambda match: match.group(1), value)
    value = _MARKDOWN_LINK.sub(lambda match: match.group(1), value)
    value = _HEADING_OR_BULLET.sub("", value)
    value = value.replace("```", "").replace("`", "")
    value = value.replace("**", "").replace("__", "")
    value = value.replace("*", "").replace("_", "")
    value = value.replace("~~", "")
    value = _MULTI_NEWLINE.sub(" ", value)
    value = _MULTI_SPACE.sub(" ", value)
    return value.strip()
