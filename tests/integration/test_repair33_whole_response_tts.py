import unittest

from core.conversation import ConversationContext, ConversationCore
from core.voice import VoiceLabEngine, VoiceProviderRegistry
from tests.integration.test_voice_pipeline_overlap import (
    Input,
    SlowOutput,
    STT,
    TwoPhraseIntelligence,
    VAD,
    TrackingTTS,
)
from core.voice import EndpointConfig


class RecordingTTS(TrackingTTS):
    def __init__(self, events):
        super().__init__(events)
        self.texts = []

    async def stream_speech(self, trace, text, voice, cancellation_token):
        self.texts.append(text)
        async for frame in super().stream_speech(
            trace, text, voice, cancellation_token
        ):
            yield frame


class Repair33WholeResponseTtsTests(unittest.IsolatedAsyncioTestCase):
    async def test_whole_mode_sends_exactly_one_complete_qwen_request(self):
        events = []
        tts = RecordingTTS(events)
        core = ConversationCore(
            context=ConversationContext("conv", "user"),
            provider=TwoPhraseIntelligence(),
        )
        engine = VoiceLabEngine(
            conversation=core,
            providers=VoiceProviderRegistry(STT(), tts),
            audio_input=Input(),
            audio_output=SlowOutput(events),
            vad=VAD(),
            endpoint_config=EndpointConfig(
                frame_ms=30,
                start_trigger_ms=60,
                end_silence_ms=60,
                preroll_ms=60,
            ),
            tts_response_mode="whole",
        )

        result = await engine.run_once()

        self.assertEqual(result.status, "completed")
        self.assertEqual(tts.calls, 1)
        self.assertEqual(len(tts.texts), 1)
        self.assertIn("First phrase is ready and useful.", tts.texts[0])
        self.assertIn("Second phrase is also ready and useful.", tts.texts[0])
        self.assertIn("luna_first_text", result.latency_ms)
        self.assertIn("luna_response_complete", result.latency_ms)
        self.assertIn("tts_first_request_started", result.latency_ms)
        self.assertGreater(result.speech_metrics["whole_response_words"], 0)

    async def test_streaming_mode_remains_separate_request_architecture(self):
        events = []
        tts = RecordingTTS(events)
        core = ConversationCore(
            context=ConversationContext("conv", "user"),
            provider=TwoPhraseIntelligence(),
        )
        engine = VoiceLabEngine(
            conversation=core,
            providers=VoiceProviderRegistry(STT(), tts),
            audio_input=Input(),
            audio_output=SlowOutput(events),
            vad=VAD(),
            endpoint_config=EndpointConfig(
                frame_ms=30,
                start_trigger_ms=60,
                end_silence_ms=60,
                preroll_ms=60,
            ),
            tts_response_mode="streaming",
        )

        result = await engine.run_once()

        self.assertEqual(result.status, "completed")
        self.assertGreaterEqual(tts.calls, 2)


if __name__ == "__main__":
    unittest.main()
