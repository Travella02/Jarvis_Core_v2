"""ORVEX-owned VAD/endpoint decision state."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum

from core.voice.contracts import AudioFrame


class EndpointSignal(str, Enum):
    NONE = "none"
    SPEECH_STARTED = "speech_started"
    SPEECH_ENDED = "speech_ended"
    MAX_DURATION = "max_duration"


@dataclass(frozen=True, slots=True)
class EndpointConfig:
    frame_ms: int = 30
    start_trigger_ms: int = 60
    end_silence_ms: int = 360
    preroll_ms: int = 240
    max_utterance_ms: int = 30_000

    def __post_init__(self) -> None:
        if self.frame_ms not in {10, 20, 30}:
            raise ValueError("frame_ms must be 10, 20, or 30 for the default WebRTC VAD path")
        for name, value in (
            ("start_trigger_ms", self.start_trigger_ms),
            ("end_silence_ms", self.end_silence_ms),
            ("preroll_ms", self.preroll_ms),
            ("max_utterance_ms", self.max_utterance_ms),
        ):
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.max_utterance_ms <= 0:
            raise ValueError("max_utterance_ms must be positive")


class EndpointDetector:
    """Turn speech/no-speech frames into deterministic endpoint signals."""

    def __init__(self, config: EndpointConfig | None = None) -> None:
        self.config = config or EndpointConfig()
        self._speech = False
        self._speech_ms = 0
        self._silence_ms = 0
        self._total_ms = 0

    @property
    def in_speech(self) -> bool:
        return self._speech

    def reset(self) -> None:
        self._speech = False
        self._speech_ms = 0
        self._silence_ms = 0
        self._total_ms = 0

    def accept(self, is_speech: bool) -> EndpointSignal:
        frame_ms = self.config.frame_ms
        if not self._speech:
            self._speech_ms = self._speech_ms + frame_ms if is_speech else 0
            if self._speech_ms >= self.config.start_trigger_ms:
                self._speech = True
                self._silence_ms = 0
                self._total_ms = self._speech_ms
                return EndpointSignal.SPEECH_STARTED
            return EndpointSignal.NONE

        self._total_ms += frame_ms
        if is_speech:
            self._silence_ms = 0
        else:
            self._silence_ms += frame_ms
            if self._silence_ms >= self.config.end_silence_ms:
                self._speech = False
                return EndpointSignal.SPEECH_ENDED

        if self._total_ms >= self.config.max_utterance_ms:
            self._speech = False
            return EndpointSignal.MAX_DURATION
        return EndpointSignal.NONE


class UtteranceBuffer:
    """Keep pre-roll and one endpointed utterance without owning VAD policy."""

    def __init__(self, config: EndpointConfig | None = None) -> None:
        self.config = config or EndpointConfig()
        preroll_frames = max(1, self.config.preroll_ms // self.config.frame_ms)
        self._preroll: deque[AudioFrame] = deque(maxlen=preroll_frames)
        self._utterance: list[AudioFrame] = []
        self._active = False

    def push(self, frame: AudioFrame, signal: EndpointSignal) -> tuple[AudioFrame, ...] | None:
        if not self._active:
            self._preroll.append(frame)
            if signal is EndpointSignal.SPEECH_STARTED:
                self._active = True
                self._utterance = list(self._preroll)
                self._preroll.clear()
            return None

        self._utterance.append(frame)
        if signal in {EndpointSignal.SPEECH_ENDED, EndpointSignal.MAX_DURATION}:
            result = tuple(self._utterance)
            self._utterance.clear()
            self._active = False
            self._preroll.clear()
            return result
        return None
