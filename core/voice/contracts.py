"""Provider-neutral contracts owned by the ORVEX realtime voice engine.

Concrete STT/TTS vendors and model names are adapter concerns. Core owns audio
shape, cancellation, lifecycle, latency semantics, and the right to replace a
provider without changing Conversation Core.
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

    @property
    def bytes_per_sample(self) -> int:
        return 2 if self.sample_format is AudioSampleFormat.PCM_S16LE else 4


@dataclass(frozen=True, slots=True)
class AudioFrame:
    trace: CorrelationContext
    sequence: int
    format: AudioFormat
    payload: bytes
    captured_at_monotonic_ns: int | None = None

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        if not isinstance(self.payload, bytes):
            raise TypeError("payload must be bytes")

    @property
    def duration_ms(self) -> float:
        frame_width = self.format.channels * self.format.bytes_per_sample
        if frame_width <= 0:
            return 0.0
        samples = len(self.payload) / frame_width
        return samples * 1000.0 / self.format.sample_rate_hz


@dataclass(frozen=True, slots=True)
class SpeechProviderMetadata:
    provider: str
    model: str
    local: bool
    streaming_input: bool
    streaming_output: bool
    voice_cloning: bool = False
    extra: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.model.strip():
            raise ValueError("provider and model must be non-empty")
        object.__setattr__(self, "extra", MappingProxyType(dict(self.extra)))


@dataclass(frozen=True, slots=True)
class SpeechProviderHealth:
    status: str
    detail: str | None = None

    @property
    def ready(self) -> bool:
        return self.status == "ready"


@dataclass(frozen=True, slots=True)
class VoiceProfile:
    """Provider-independent voice identity/configuration reference.

    A profile may point to an ORVEX-curated voice, a user-consented local
    reference clip, or a future cloud-provider voice. Callers do not depend on
    vendor schemas. Rights/consent persistence belongs to Voice Studio later.
    """

    profile_id: str
    display_name: str
    provider_hint: str | None = None
    provider_voice_id: str | None = None
    reference_audio_path: str | None = None
    settings: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.profile_id.strip():
            raise ValueError("profile_id must be non-empty")
        if not self.display_name.strip():
            raise ValueError("display_name must be non-empty")
        object.__setattr__(self, "settings", MappingProxyType(dict(self.settings)))


class TranscriptionEventType(str, Enum):
    PARTIAL = "partial"
    FINAL = "final"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class TranscriptionEvent:
    trace: CorrelationContext
    event_type: TranscriptionEventType
    text: str = ""
    confidence: float | None = None
    detail: str | None = None
    audio_end_ms: int | None = None

    def __post_init__(self) -> None:
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.audio_end_ms is not None and self.audio_end_ms < 0:
            raise ValueError("audio_end_ms must be non-negative")


class SpeechToTextProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> SpeechProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    async def health(self) -> SpeechProviderHealth:
        raise NotImplementedError

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
    @property
    @abstractmethod
    def metadata(self) -> SpeechProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    async def health(self) -> SpeechProviderHealth:
        raise NotImplementedError

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
