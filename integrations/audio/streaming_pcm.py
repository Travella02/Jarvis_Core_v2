"""Provider-neutral helpers for continuous PCM16 playback streams.

GPT-Live and future duplex providers deliver arbitrary network audio chunks.
This module converts those chunks into stable fixed-duration PCM frames, keeps a
small playback cushion so ordinary packet jitter does not starve PortAudio, and
ramps interruption cutoffs to zero instead of dropping the waveform abruptly.

Nothing here depends on OpenAI or a specific voice model.
"""

from __future__ import annotations

import asyncio
import math
import sys
from array import array
from collections.abc import AsyncIterator
from dataclasses import dataclass
from time import monotonic


_CLOSE = object()
_INTERRUPT_FADE = object()
_INTERRUPT_CLEAR = object()


def _samples_from_pcm16(payload: bytes) -> array:
    if len(payload) % 2:
        raise ValueError("PCM16 payload must contain whole samples")
    values = array("h")
    values.frombytes(payload)
    if sys.byteorder != "little":  # pragma: no cover - Windows/x86 lab is little-endian
        values.byteswap()
    return values


def _pcm16_from_samples(values: array) -> bytes:
    if sys.byteorder == "little":
        return values.tobytes()
    copy = array("h", values)
    copy.byteswap()
    return copy.tobytes()


@dataclass(frozen=True, slots=True)
class StreamingPCMBufferStats:
    interruptions: int = 0
    dropped_bytes: int = 0
    padded_tail_bytes: int = 0


class StreamingPCM16PlaybackBuffer:
    """Condition an arbitrary mono PCM16 byte stream for continuous playback.

    The producer may append chunks of any even byte length. The consumer sees
    fixed-size frames. Playback initially waits for ``prebuffer_ms`` of source
    audio and automatically rebuilds that cushion after an underrun. A long gap
    flushes a short partial tail with silence so the tail of one utterance is not
    glued to the beginning of the next one.

    ``interrupt()`` drops only not-yet-consumed PCM and emits a tiny ramp from
    the last delivered sample to zero. This makes conversational barge-in much
    less likely to create an audible click than a hard discontinuity.
    """

    def __init__(
        self,
        *,
        sample_rate_hz: int,
        frame_ms: int = 20,
        prebuffer_ms: int = 40,
        fade_ms: int = 5,
        gap_flush_ms: int = 250,
    ) -> None:
        if sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        if frame_ms <= 0:
            raise ValueError("frame_ms must be positive")
        if prebuffer_ms < 0 or fade_ms < 0 or gap_flush_ms <= 0:
            raise ValueError("buffer timings are invalid")
        frame_samples = round(sample_rate_hz * frame_ms / 1000)
        if frame_samples <= 0:
            raise ValueError("frame_ms produces an empty PCM frame")
        self.sample_rate_hz = sample_rate_hz
        self.frame_ms = frame_ms
        self.prebuffer_ms = prebuffer_ms
        self.fade_ms = fade_ms
        self.gap_flush_ms = gap_flush_ms
        self.frame_samples = frame_samples
        self.frame_bytes = frame_samples * 2
        self.prebuffer_frames = max(1, math.ceil(max(frame_ms, prebuffer_ms) / frame_ms))
        self.fade_samples = min(frame_samples, round(sample_rate_hz * fade_ms / 1000))
        self._pending = bytearray()
        self._queue: asyncio.Queue[bytes | object] = asyncio.Queue()
        self._last_append_at: float | None = None
        self._last_emitted_sample = 0
        self._last_emitted_at: float | None = None
        self._closed = False
        self._interruptions = 0
        self._dropped_bytes = 0
        self._padded_tail_bytes = 0

    @property
    def stats(self) -> StreamingPCMBufferStats:
        return StreamingPCMBufferStats(
            interruptions=self._interruptions,
            dropped_bytes=self._dropped_bytes,
            padded_tail_bytes=self._padded_tail_bytes,
        )

    def append(self, payload: bytes) -> None:
        if self._closed:
            raise RuntimeError("cannot append after playback buffer close")
        if not payload:
            return
        if len(payload) % 2:
            raise ValueError("PCM16 payload must contain whole samples")
        now = monotonic()
        if (
            self._last_append_at is not None
            and (now - self._last_append_at) * 1000.0 >= self.gap_flush_ms
            and self._pending
        ):
            self._flush_partial_with_silence()
        self._last_append_at = now
        self._pending.extend(payload)
        self._emit_complete_frames()

    def interrupt(self) -> None:
        if self._closed:
            return
        self._interruptions += 1
        self._dropped_bytes += len(self._pending)
        self._pending.clear()
        while True:
            try:
                item = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if isinstance(item, bytes):
                self._dropped_bytes += len(item)
        recent_playback = (
            self._last_emitted_at is not None
            and (monotonic() - self._last_emitted_at) * 1000.0 <= 160.0
        )
        self._queue.put_nowait(_INTERRUPT_FADE if recent_playback else _INTERRUPT_CLEAR)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._pending:
            self._flush_partial_with_silence()
        self._queue.put_nowait(_CLOSE)

    def _emit_complete_frames(self) -> None:
        while len(self._pending) >= self.frame_bytes:
            payload = bytes(self._pending[: self.frame_bytes])
            del self._pending[: self.frame_bytes]
            self._queue.put_nowait(payload)

    def _flush_partial_with_silence(self) -> None:
        if not self._pending:
            return
        original = len(self._pending)
        self._pending.extend(b"\x00" * (self.frame_bytes - len(self._pending)))
        self._padded_tail_bytes += self.frame_bytes - original
        payload = bytes(self._pending)
        self._pending.clear()
        self._queue.put_nowait(payload)

    def _fade_frame(self) -> bytes:
        if self._last_emitted_sample == 0 or self.fade_samples <= 0:
            return b"\x00" * self.frame_bytes
        values = array("h")
        start = self._last_emitted_sample
        for index in range(self.fade_samples):
            fraction = (index + 1) / self.fade_samples
            values.append(round(start * (1.0 - fraction)))
        if len(values) < self.frame_samples:
            values.extend([0] * (self.frame_samples - len(values)))
        return _pcm16_from_samples(values)

    @staticmethod
    def _fade_in(payload: bytes, fade_samples: int) -> bytes:
        if fade_samples <= 0:
            return payload
        values = _samples_from_pcm16(payload)
        limit = min(fade_samples, len(values))
        for index in range(limit):
            fraction = (index + 1) / limit
            values[index] = round(values[index] * fraction)
        return _pcm16_from_samples(values)

    async def frames(self) -> AsyncIterator[bytes]:
        rebuffer = True
        first_after_rebuffer = True
        staged: list[bytes] = []
        while True:
            item = await self._queue.get()
            if item is _CLOSE:
                for payload in staged:
                    self._last_emitted_sample = _samples_from_pcm16(payload)[-1]
                    self._last_emitted_at = monotonic()
                    yield payload
                return
            if item is _INTERRUPT_FADE or item is _INTERRUPT_CLEAR:
                staged.clear()
                if item is _INTERRUPT_FADE:
                    fade = self._fade_frame()
                    self._last_emitted_sample = 0
                    self._last_emitted_at = monotonic()
                    yield fade
                else:
                    self._last_emitted_sample = 0
                rebuffer = True
                first_after_rebuffer = True
                continue
            assert isinstance(item, bytes)
            if rebuffer:
                staged.append(item)
                if len(staged) < self.prebuffer_frames:
                    continue
                for index, payload in enumerate(staged):
                    if index == 0 and first_after_rebuffer:
                        payload = self._fade_in(payload, self.fade_samples)
                    values = _samples_from_pcm16(payload)
                    self._last_emitted_sample = values[-1] if values else 0
                    self._last_emitted_at = monotonic()
                    yield payload
                staged.clear()
                rebuffer = False
                first_after_rebuffer = False
                continue

            payload = item
            values = _samples_from_pcm16(payload)
            self._last_emitted_sample = values[-1] if values else 0
            self._last_emitted_at = monotonic()
            yield payload
            if self._queue.empty():
                rebuffer = True
                first_after_rebuffer = True
