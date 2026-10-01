"""Provider-neutral audio-device contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.voice.contracts import AudioFormat, AudioFrame


@dataclass(frozen=True, slots=True)
class AudioDeviceInfo:
    device_id: str
    name: str
    max_input_channels: int = 0
    max_output_channels: int = 0
    default_sample_rate_hz: int | None = None
    host_api: str | None = None


@dataclass(frozen=True, slots=True)
class AudioPlaybackResult:
    bytes_written: int
    # Time the first PCM write was submitted to the audio backend. Earlier
    # repairs recorded this after blocking RawOutputStream.write() returned,
    # making one full PCM frame look like playback-start latency.
    first_write_monotonic_ns: int | None = None
    first_write_completed_monotonic_ns: int | None = None
    estimated_first_audible_monotonic_ns: int | None = None
    output_latency_ms: float | None = None
    low_latency_requested: bool = False
    low_latency_active: bool = False
    source_duration_ms_written: float = 0.0

    def __post_init__(self) -> None:
        if self.bytes_written < 0:
            raise ValueError("bytes_written must be non-negative")
        if self.output_latency_ms is not None and self.output_latency_ms < 0:
            raise ValueError("output_latency_ms must be non-negative")
        if self.source_duration_ms_written < 0:
            raise ValueError("source_duration_ms_written must be non-negative")


class AudioInput(ABC):
    @abstractmethod
    async def devices(self) -> tuple[AudioDeviceInfo, ...]:
        raise NotImplementedError

    @abstractmethod
    async def stream(
        self,
        *,
        trace: CorrelationContext,
        audio_format: AudioFormat,
        frame_ms: int,
        cancellation_token: CancellationToken,
    ) -> AsyncIterator[AudioFrame]:
        raise NotImplementedError


class AudioOutput(ABC):
    @abstractmethod
    async def devices(self) -> tuple[AudioDeviceInfo, ...]:
        raise NotImplementedError

    @abstractmethod
    async def play(
        self,
        audio: AsyncIterator[AudioFrame],
        cancellation_token: CancellationToken,
    ) -> AudioPlaybackResult:
        """Play frames and report physically written PCM bytes/first-write time."""
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError
