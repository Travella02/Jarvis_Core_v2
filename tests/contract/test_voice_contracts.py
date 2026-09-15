import unittest
from collections.abc import AsyncIterator

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.voice import (
    AudioFormat,
    AudioFrame,
    SpeechToTextProvider,
    TextToSpeechProvider,
    TranscriptionEvent,
    TranscriptionEventType,
    VoiceProfile,
)


async def one_frame(trace: CorrelationContext) -> AsyncIterator[AudioFrame]:
    yield AudioFrame(trace=trace, sequence=0, format=AudioFormat(16000), payload=b"\x00\x00")


class FakeSTT(SpeechToTextProvider):
    async def stream_transcription(self, audio, cancellation_token):
        async for frame in audio:
            cancellation_token.raise_if_cancelled()
            yield TranscriptionEvent(frame.trace, TranscriptionEventType.FINAL, text="hello")

    async def cancel(self, request_id: str) -> None:
        return None


class FakeTTS(TextToSpeechProvider):
    async def stream_speech(self, trace, text, voice, cancellation_token):
        cancellation_token.raise_if_cancelled()
        yield AudioFrame(trace=trace, sequence=0, format=AudioFormat(24000), payload=text.encode())

    async def cancel(self, request_id: str) -> None:
        return None


class VoiceContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_stt_and_tts_are_replaceable_contracts(self) -> None:
        trace = CorrelationContext("corr", "req")
        token = CancellationToken()
        stt_events = [event async for event in FakeSTT().stream_transcription(one_frame(trace), token)]
        self.assertEqual(stt_events[0].text, "hello")

        voice = VoiceProfile("default", "Default")
        tts_frames = [frame async for frame in FakeTTS().stream_speech(trace, "hello", voice, token)]
        self.assertEqual(tts_frames[0].payload, b"hello")


if __name__ == "__main__":
    unittest.main()
