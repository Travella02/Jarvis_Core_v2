from __future__ import annotations

import unittest
from collections.abc import AsyncIterator

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.voice import (
    AudioFrame,
    LocalWakeListener,
    SpeechProviderHealth,
    SpeechProviderMetadata,
    SpeechToTextProvider,
    TranscriptionEvent,
    TranscriptionEventType,
    WAKE_AUDIO_FORMAT,
    WAKE_FRAME_BYTES,
    WakeSleepConfig,
)
from core.voice.endpointing import EndpointConfig
from core.voice.vad import VoiceActivityDetector


class FakeVad(VoiceActivityDetector):
    def __init__(self, decisions: list[bool]) -> None:
        self.decisions = list(decisions)
        self.reset_count = 0
        self.closed = False

    def is_speech(self, frame: AudioFrame) -> bool:
        return self.decisions.pop(0) if self.decisions else False

    def reset(self) -> None:
        self.reset_count += 1

    def close(self) -> None:
        self.closed = True


class FakeStt(SpeechToTextProvider):
    def __init__(self, transcripts: list[str]) -> None:
        self.transcripts = list(transcripts)
        self.warmup_count = 0
        self.closed = False
        self.audio_frames_seen: list[int] = []

    @property
    def metadata(self) -> SpeechProviderMetadata:
        return SpeechProviderMetadata(
            provider="fake-local-stt",
            model="fake",
            local=True,
            streaming_input=True,
            streaming_output=False,
        )

    async def health(self) -> SpeechProviderHealth:
        return SpeechProviderHealth("ready", "local fake ready")

    async def warmup(self) -> None:
        self.warmup_count += 1

    async def stream_transcription(
        self,
        audio: AsyncIterator[AudioFrame],
        cancellation_token: CancellationToken,
    ) -> AsyncIterator[TranscriptionEvent]:
        frames = [frame async for frame in audio]
        self.audio_frames_seen.append(len(frames))
        text = self.transcripts.pop(0) if self.transcripts else ""
        yield TranscriptionEvent(
            trace=frames[0].trace if frames else CorrelationContext.create(),
            event_type=TranscriptionEventType.FINAL,
            text=text,
            confidence=0.97,
        )

    async def cancel(self, request_id: str) -> None:
        return None

    async def close(self) -> None:
        self.closed = True


def listener_for(transcript: str, decisions: list[bool] | None = None) -> tuple[LocalWakeListener, FakeStt, FakeVad]:
    stt = FakeStt([transcript])
    vad = FakeVad(decisions or [True, False])
    listener = LocalWakeListener(
        stt=stt,
        vad=vad,
        config=WakeSleepConfig(wake_phrases=("hey jarvis", "jarvis")),
        endpoint_config=EndpointConfig(
            frame_ms=30,
            start_trigger_ms=30,
            end_silence_ms=30,
            preroll_ms=30,
            max_utterance_ms=3000,
        ),
    )
    return listener, stt, vad


class LocalWakeListenerTests(unittest.IsolatedAsyncioTestCase):
    async def test_complete_local_utterance_wakes_and_preserves_opening_command(self) -> None:
        listener, stt, _ = listener_for("Hey Jarvis, tell me something about space")
        frame = b"\x01\x00" * (WAKE_FRAME_BYTES // 2)
        self.assertIsNone(await listener.feed_pcm(frame))
        result = await listener.feed_pcm(frame)
        self.assertIsNotNone(result)
        assert result is not None and result.match is not None
        self.assertTrue(result.woke)
        self.assertEqual(result.match.phrase, "hey jarvis")
        self.assertEqual(result.match.command_text, "tell me something about space")
        self.assertEqual(result.confidence, 0.97)
        self.assertEqual(stt.audio_frames_seen, [2])

    async def test_non_wake_speech_is_transcribed_locally_but_does_not_wake(self) -> None:
        listener, _, _ = listener_for("someone on the television said hello")
        frame = b"\x00\x00" * (WAKE_FRAME_BYTES // 2)
        await listener.feed_pcm(frame)
        result = await listener.feed_pcm(frame)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertFalse(result.woke)
        self.assertIsNone(result.match)

    async def test_wake_phrase_without_remainder_opens_conversation_without_inventing_command(self) -> None:
        listener, _, _ = listener_for("Jarvis")
        frame = b"\x00\x00" * (WAKE_FRAME_BYTES // 2)
        await listener.feed_pcm(frame)
        result = await listener.feed_pcm(frame)
        assert result is not None and result.match is not None
        self.assertEqual(result.match.command_text, "")

    async def test_pcm_contract_is_exact_16khz_30ms_mono_pcm16(self) -> None:
        listener, _, _ = listener_for("Jarvis")
        self.assertEqual(WAKE_AUDIO_FORMAT.sample_rate_hz, 16_000)
        self.assertEqual(WAKE_FRAME_BYTES, 960)
        with self.assertRaisesRegex(ValueError, "exactly 960 bytes"):
            await listener.feed_pcm(b"\x00" * 958)

    async def test_warmup_and_close_are_provider_owned_and_local(self) -> None:
        listener, stt, vad = listener_for("Jarvis")
        health = await listener.health()
        self.assertTrue(health.ready)
        await listener.warmup()
        self.assertEqual(stt.warmup_count, 1)
        await listener.close()
        self.assertTrue(stt.closed)
        self.assertTrue(vad.closed)
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await listener.feed_pcm(b"\x00" * WAKE_FRAME_BYTES)


if __name__ == "__main__":
    unittest.main()
