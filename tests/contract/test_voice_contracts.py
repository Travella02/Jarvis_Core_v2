import unittest
from collections.abc import AsyncIterator

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.voice import (
    AudioFormat,
    AudioFrame,
    SpeechProviderHealth,
    SpeechProviderMetadata,
    SpeechToTextProvider,
    TextToSpeechProvider,
    TranscriptionEvent,
    TranscriptionEventType,
    VoiceProfile,
)


async def one_frame(trace: CorrelationContext) -> AsyncIterator[AudioFrame]:
    yield AudioFrame(trace=trace, sequence=0, format=AudioFormat(16000), payload=b"\x00\x00")


class FakeSTT(SpeechToTextProvider):
    @property
    def metadata(self):
        return SpeechProviderMetadata("fake-stt", "fake", True, True, True)

    async def health(self):
        return SpeechProviderHealth("ready")

    async def stream_transcription(self, audio, cancellation_token):
        async for frame in audio:
            cancellation_token.raise_if_cancelled()
            yield TranscriptionEvent(frame.trace, TranscriptionEventType.FINAL, text="hello")

    async def cancel(self, request_id: str) -> None:
        return None


class FakeTTS(TextToSpeechProvider):
    @property
    def metadata(self):
        return SpeechProviderMetadata("fake-tts", "fake", True, False, True)

    async def health(self):
        return SpeechProviderHealth("ready")

    async def stream_speech(self, trace, text, voice, cancellation_token):
        cancellation_token.raise_if_cancelled()
        yield AudioFrame(trace=trace, sequence=0, format=AudioFormat(24000), payload=text.encode())

    async def cancel(self, request_id: str) -> None:
        return None


class VoiceContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_stt_and_tts_are_replaceable_contracts(self) -> None:
        trace = CorrelationContext("corr", "req")
        token = CancellationToken()
        stt = FakeSTT()
        self.assertTrue((await stt.health()).ready)
        self.assertEqual(stt.metadata.provider, "fake-stt")
        stt_events = [event async for event in stt.stream_transcription(one_frame(trace), token)]
        self.assertEqual(stt_events[0].text, "hello")

        voice = VoiceProfile("default", "Default")
        tts = FakeTTS()
        self.assertTrue((await tts.health()).ready)
        self.assertEqual(tts.metadata.provider, "fake-tts")
        tts_frames = [frame async for frame in tts.stream_speech(trace, "hello", voice, token)]
        self.assertEqual(tts_frames[0].payload, b"hello")

    def test_voice_profile_is_provider_neutral_and_supports_reference_audio(self) -> None:
        profile = VoiceProfile(
            "mine",
            "My voice",
            reference_audio_path="C:/voices/mine.wav",
            settings={"temperature": 0.7},
        )
        self.assertEqual(profile.reference_audio_path, "C:/voices/mine.wav")
        self.assertEqual(profile.settings["temperature"], 0.7)
        with self.assertRaises(TypeError):
            profile.settings["temperature"] = 1.0


if __name__ == "__main__":
    unittest.main()
