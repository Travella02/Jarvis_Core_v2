"""Voice-activity contract. Concrete algorithms are replaceable."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.voice.contracts import AudioFrame


class VoiceActivityDetector(ABC):
    @abstractmethod
    def is_speech(self, frame: AudioFrame) -> bool:
        raise NotImplementedError
