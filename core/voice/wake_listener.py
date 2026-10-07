"""Provider-neutral local wake listener for Jarvis desktop lifecycle.

The desktop keeps sleeping audio on-device and sends 16 kHz mono PCM only to the
loopback Core host. Silero decides whether speech is present, Whisper supplies the
words after a local endpoint, and WakePhraseDetector decides whether the complete
utterance begins with a configured wake phrase. Nothing leaves the machine while
Jarvis is asleep.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.voice.contracts import (
    AudioFormat,
    AudioFrame,
    AudioSampleFormat,
    SpeechProviderHealth,
    SpeechToTextProvider,
    TranscriptionEventType,
)
from core.voice.conversation_control import WakeMatch, WakePhraseDetector, WakeSleepConfig
from core.voice.endpointing import EndpointConfig, EndpointDetector, EndpointSignal, UtteranceBuffer
from core.voice.vad import VoiceActivityDetector


WAKE_AUDIO_FORMAT = AudioFormat(
    sample_rate_hz=16_000,
    channels=1,
    sample_format=AudioSampleFormat.PCM_S16LE,
)
WAKE_FRAME_MS = 30
WAKE_FRAME_BYTES = int(WAKE_AUDIO_FORMAT.sample_rate_hz * (WAKE_FRAME_MS / 1000.0)) * 2


@dataclass(frozen=True, slots=True)
class WakeListenerResult:
    transcript: str
    match: WakeMatch | None
    confidence: float | None = None

    @property
    def woke(self) -> bool:
        return self.match is not None


class LocalWakeListener:
    """Consume local PCM frames and return completed wake-phrase decisions.

    The class owns no microphone or network transport. The caller supplies PCM
    frames, which lets Electron keep the one physical microphone while sleeping
    and lets a different client transport replace Electron later without changing
    wake-word policy.
    """

    def __init__(
        self,
        *,
        stt: SpeechToTextProvider,
        vad: VoiceActivityDetector,
        config: WakeSleepConfig | None = None,
        endpoint_config: EndpointConfig | None = None,
    ) -> None:
        self.stt = stt
        self.vad = vad
        self.config = config or WakeSleepConfig()
        self.endpoint_config = endpoint_config or EndpointConfig(
            frame_ms=WAKE_FRAME_MS,
            start_trigger_ms=60,
            end_silence_ms=420,
            preroll_ms=300,
            max_utterance_ms=20_000,
        )
        self.wake_detector = WakePhraseDetector(self.config.wake_phrases)
        self._sequence = 0
        self._trace = CorrelationContext.create()
        self._endpoint = EndpointDetector(self.endpoint_config)
        self._buffer = UtteranceBuffer(self.endpoint_config)
        self._closed = False

    async def health(self) -> SpeechProviderHealth:
        return await self.stt.health()

    async def warmup(self) -> None:
        warmup = getattr(self.stt, "warmup", None)
        if callable(warmup):
            await warmup()

    def reset(self) -> None:
        self._sequence = 0
        self._trace = CorrelationContext.create()
        self._endpoint.reset()
        self._buffer = UtteranceBuffer(self.endpoint_config)
        self.vad.reset()

    async def feed_pcm(self, payload: bytes) -> WakeListenerResult | None:
        if self._closed:
            raise RuntimeError("wake listener is closed")
        if len(payload) != WAKE_FRAME_BYTES:
            raise ValueError(
                f"wake PCM frame must be exactly {WAKE_FRAME_BYTES} bytes "
                f"({WAKE_FRAME_MS} ms at 16 kHz mono PCM16); got {len(payload)}"
            )

        frame = AudioFrame(
            trace=self._trace,
            sequence=self._sequence,
            format=WAKE_AUDIO_FORMAT,
            payload=bytes(payload),
        )
        self._sequence += 1
        is_speech = self.vad.is_speech(frame)
        signal = self._endpoint.accept(is_speech)
        utterance = self._buffer.push(frame, signal)
        if utterance is None:
            return None

        try:
            transcript, confidence = await self._transcribe(utterance)
        finally:
            self.reset()

        clean = transcript.strip()
        match = self.wake_detector.match(clean) if clean else None
        return WakeListenerResult(transcript=clean, match=match, confidence=confidence)

    async def _transcribe(self, frames: tuple[AudioFrame, ...]) -> tuple[str, float | None]:
        token = CancellationToken()

        async def audio() -> AsyncIterator[AudioFrame]:
            for frame in frames:
                yield frame

        final_text = ""
        final_confidence: float | None = None
        async for event in self.stt.stream_transcription(audio(), token):
            if event.event_type is TranscriptionEventType.FINAL:
                final_text = event.text
                final_confidence = event.confidence
            elif event.event_type is TranscriptionEventType.ERROR:
                raise RuntimeError(event.detail or "wake transcription failed")
        return final_text, final_confidence

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close_stt = getattr(self.stt, "close", None)
        if callable(close_stt):
            await close_stt()
        close_vad = getattr(self.vad, "close", None)
        if callable(close_vad):
            close_vad()
