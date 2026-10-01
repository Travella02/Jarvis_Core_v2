"""Voice-activity contract. Concrete algorithms are replaceable."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.voice.contracts import AudioFrame


class VoiceActivityDetector(ABC):
    @abstractmethod
    def is_speech(self, frame: AudioFrame) -> bool:
        raise NotImplementedError

    def reset(self) -> None:
        """Reset streaming detector state between utterances when supported."""

    def close(self) -> None:
        """Release provider resources when supported."""
