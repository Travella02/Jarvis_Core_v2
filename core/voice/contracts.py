"""ORVEX-owned voice-engine contracts.

0.0.1 defines boundaries only. Audio capture, VAD, endpointing, AEC/noise
handling, interruption orchestration, and concrete STT/TTS providers are later
milestones.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext


class AudioSampleFormat(str, Enum):
    PCM_S16LE = "pcm_s16le"
    PCM_F32LE = "pcm_f32le"


@dataclass(frozen=True, slots=True)
class AudioFormat:
    sample_rate_hz: int
    channels: int = 1
    sample_format: AudioSampleFormat = AudioSampleFormat.PCM_S16LE

    def __post_init__(self) -> None:
        if self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        if self.channels <= 0:
            raise ValueError("channels must be positive")


@dataclass(frozen=True, slots=True)
class AudioFrame:
    trace: CorrelationContext
    sequence: int
    format: AudioFormat
    payload: bytes
    captured_at_monotonic_ns: int | None = None


@dataclass(frozen=True, slots=True)
class VoiceProfile:
    """Provider-independent voice identity/configuration reference.

    Rights/consent enforcement and persistent Voice Studio behavior are later
    work; this contract prevents TTS callers from depending on vendor schemas.
    """

    profile_id: str
    display_name: str
    provider_hint: str | None = None
    provider_voice_id: str | None = None
    settings: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.profile_id.strip():
            raise ValueError("profile_id must be non-empty")
        object.__setattr__(self, "settings", MappingProxyType(dict(self.settings)))


class TranscriptionEventType(str, Enum):
    PARTIAL = "partial"
    FINAL = "final"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class TranscriptionEvent:
    trace: CorrelationContext
    event_type: TranscriptionEventType
    text: str = ""
    confidence: float | None = None
    detail: str | None = None


class SpeechToTextProvider(ABC):
    @abstractmethod
    async def stream_transcription(
        self,
        audio: AsyncIterator[AudioFrame],
        cancellation_token: CancellationToken,
    ) -> AsyncIterator[TranscriptionEvent]:
        raise NotImplementedError

    @abstractmethod
    async def cancel(self, request_id: str) -> None:
        raise NotImplementedError


class TextToSpeechProvider(ABC):
    @abstractmethod
    async def stream_speech(
        self,
        trace: CorrelationContext,
        text: str,
        voice: VoiceProfile,
        cancellation_token: CancellationToken,
    ) -> AsyncIterator[AudioFrame]:
        raise NotImplementedError

    @abstractmethod
    async def cancel(self, request_id: str) -> None:
        raise NotImplementedError
