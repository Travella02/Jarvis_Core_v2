"""Provider-neutral WebRTC framing helpers.

SDP is a framed wire protocol.  Keep normalization outside any one voice
provider so GPT-Live, Realtime, and future WebRTC frontends share the same
accepted CRLF/terminal-CRLF behavior.
"""

from __future__ import annotations


def normalize_sdp(value: str | bytes, *, label: str) -> str:
    """Return canonical UTF-8 SDP with CRLF framing and a final CRLF."""

    if isinstance(value, bytes):
        try:
            text = value.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{label} was not valid UTF-8 SDP") from exc
    else:
        text = str(value or "").removeprefix("\ufeff")

    if "\x00" in text:
        raise ValueError(f"{label} contained an invalid null byte")

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines or lines[0].strip() != "v=0":
        raise ValueError(f"{label} did not begin with v=0")

    normalized_lines: list[str] = []
    for index, line in enumerate(lines, start=1):
        cleaned = line.rstrip(" \t")
        if not cleaned:
            raise ValueError(f"{label} contained an empty SDP line at {index}")
        if cleaned[0].isspace():
            raise ValueError(f"{label} contained leading whitespace at SDP line {index}")
        if any(ord(char) < 32 and char != "\t" for char in cleaned):
            raise ValueError(f"{label} contained an invalid control character at SDP line {index}")
        normalized_lines.append(cleaned)

    return "\r\n".join(normalized_lines) + "\r\n"
