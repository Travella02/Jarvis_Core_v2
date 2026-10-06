"""Provider-neutral full-duplex voice-frontend contracts.

0.0.9 introduces a boundary above STT/TTS so Jarvis can use a native full-duplex
voice service without making that service the owner of reasoning, memory, tools,
permissions, tasks, or durable state.  The accepted local Whisper/Luna/Qwen path
remains available in parallel.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, slots=True)
class VoiceFrontendMetadata:
    provider: str
    model: str
    local: bool
    full_duplex: bool
    client_delegation: bool

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.model.strip():
            raise ValueError("provider and model must be non-empty")


@dataclass(frozen=True, slots=True)
class VoiceFrontendHealth:
    status: str
    detail: str | None = None

    @property
    def ready(self) -> bool:
        return self.status in {"ready", "configured"}


@dataclass(frozen=True, slots=True)
class VoiceFrontendSessionConfig:
    instructions: str
    voice: str
    sample_rate_hz: int = 16_000
    history: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    store: bool = False

    def __post_init__(self) -> None:
        if not self.instructions.strip():
            raise ValueError("instructions must be non-empty")
        if not self.voice.strip():
            raise ValueError("voice must be non-empty")
        if self.sample_rate_hz not in {8_000, 16_000, 24_000}:
            raise ValueError("sample_rate_hz must be 8000, 16000, or 24000")
        frozen_history = tuple(MappingProxyType(dict(item)) for item in self.history)
        object.__setattr__(self, "history", frozen_history)


class VoiceFrontendEventType(str, Enum):
    SESSION_STARTED = "session_started"
    INPUT_TRANSCRIPT_DELTA = "input_transcript_delta"
    OUTPUT_TRANSCRIPT_DELTA = "output_transcript_delta"
    OUTPUT_AUDIO = "output_audio"
    DELEGATION_REQUESTED = "delegation_requested"
    USAGE_UPDATED = "usage_updated"
    SESSION_CLOSED = "session_closed"
    INFO = "info"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class VoiceFrontendEvent:
    event_type: VoiceFrontendEventType
    text: str = ""
    audio: bytes = b""
    delegation_id: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    offset_ms: int | None = None
    usage_seconds: float | None = None
    detail: str | None = None
    raw_type: str | None = None

    def __post_init__(self) -> None:
        if self.start_ms is not None and self.start_ms < 0:
            raise ValueError("start_ms must be non-negative")
        if self.end_ms is not None and self.end_ms < 0:
            raise ValueError("end_ms must be non-negative")
        if self.offset_ms is not None and self.offset_ms < 0:
            raise ValueError("offset_ms must be non-negative")
        if self.usage_seconds is not None and self.usage_seconds < 0:
            raise ValueError("usage_seconds must be non-negative")


class VoiceFrontendSession(ABC):
    """One connected full-duplex voice session.

    Core owns the backend workflow.  A frontend session transports microphone
    audio, speaker audio, transcript observations, and delegation requests.
    """

    @property
    @abstractmethod
    def session_id(self) -> str | None:
        raise NotImplementedError

    @abstractmethod
    async def send_audio(self, pcm_bytes: bytes) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_commentary(self, delegation_id: str, content: str) -> None:
        """Send verified backend content that the voice frontend may speak."""
        raise NotImplementedError

    @abstractmethod
    async def send_thinking(self, delegation_id: str, content: str) -> None:
        """Send quiet task/progress context that should not be spoken immediately."""
        raise NotImplementedError

    @abstractmethod
    async def append_instructions(self, content: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def events(self) -> AsyncIterator[VoiceFrontendEvent]:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError


class VoiceFrontendProvider(ABC):
    """Replaceable native-conversation voice frontend provider."""

    @property
    @abstractmethod
    def metadata(self) -> VoiceFrontendMetadata:
        raise NotImplementedError

    @abstractmethod
    async def health(self) -> VoiceFrontendHealth:
        raise NotImplementedError

    @abstractmethod
    async def open_session(self, config: VoiceFrontendSessionConfig) -> VoiceFrontendSession:
        raise NotImplementedError
