import asyncio
import unittest
from time import monotonic_ns

from core.common.cancellation import CancellationToken
from core.conversation import ConversationContext, ConversationCore
from core.intelligence import (
    ContextLimits,
    IntelligenceEvent,
    IntelligenceEventType,
    IntelligenceProvider,
    ProviderHealth,
    ProviderHealthState,
    ProviderMetadata,
)
from core.voice import (
    AudioDeviceInfo,
    AudioFormat,
    AudioFrame,
    AudioInput,
    AudioOutput,
    AudioPlaybackResult,
    EndpointConfig,
    SpeechProviderHealth,
    SpeechProviderMetadata,
    SpeechToTextProvider,
    TextToSpeechProvider,
    TranscriptionEvent,
    TranscriptionEventType,
    VoiceActivityDetector,
    VoiceLabEngine,
    VoiceProviderRegistry,
)


class TwoPhraseIntelligence(IntelligenceProvider):
    @property
    def metadata(self): return ProviderMetadata("fake", "fake")
    def supports_tools(self): return False
    def supports_vision(self): return False
    def supports_reasoning_levels(self): return True
    def context_limits(self): return ContextLimits(1000, 1000)
    async def health(self): return ProviderHealth(ProviderHealthState.HEALTHY)
    async def cancel(self, request_id): return None

    async def stream_response(self, context, tools, reasoning_policy, cancellation_token):
        yield IntelligenceEvent(IntelligenceEventType.TEXT_DELTA, text_delta="First phrase is ready and useful. ")
        await asyncio.sleep(0)
        yield IntelligenceEvent(IntelligenceEventType.TEXT_DELTA, text_delta="Second phrase is also ready and useful.")
        yield IntelligenceEvent(IntelligenceEventType.COMPLETED)


class Input(AudioInput):
    async def devices(self): return (AudioDeviceInfo("0", "fake", 1, 0, 16000),)
    async def stream(self, *, trace, audio_format, frame_ms, cancellation_token):
        samples = int(audio_format.sample_rate_hz * frame_ms / 1000)
        for seq, speech in enumerate((True, True, True, True, True, True, True, True, False, False)):
            sample = 10000 if speech else 0
            payload = int(sample).to_bytes(2, "little", signed=True) * samples
            yield AudioFrame(trace, seq, audio_format, payload)
            await asyncio.sleep(0)


class VAD(VoiceActivityDetector):
    def is_speech(self, frame): return int.from_bytes(frame.payload[:2], "little", signed=True) != 0


class STT(SpeechToTextProvider):
    @property
    def metadata(self): return SpeechProviderMetadata("fake-stt", "fake", True, True, True)
    async def health(self): return SpeechProviderHealth("ready")
    async def cancel(self, request_id): return None
    async def stream_transcription(self, audio, cancellation_token):
        first = None
        async for frame in audio:
            first = first or frame
        yield TranscriptionEvent(first.trace, TranscriptionEventType.FINAL, "hello")


class TrackingTTS(TextToSpeechProvider):
    def __init__(self, events):
        self.events = events
        self.calls = 0

    @property
    def metadata(self): return SpeechProviderMetadata("fake-tts", "fake", True, False, True)
    async def health(self): return SpeechProviderHealth("ready")
    async def cancel(self, request_id): return None
    async def stream_speech(self, trace, text, voice, cancellation_token):
        self.calls += 1
        self.events.append(f"tts{self.calls}_start")
        yield AudioFrame(trace, 0, AudioFormat(24000), b"audio")


class SlowOutput(AudioOutput):
    def __init__(self, events): self.events = events
    async def devices(self): return (AudioDeviceInfo("0", "fake", 0, 1, 24000),)
    async def stop(self): return None
    async def play(self, audio, cancellation_token: CancellationToken):
        total = 0
        first = None
        async for frame in audio:
            first = first or monotonic_ns()
            total += len(frame.payload)
            self.events.append("play_frame")
            await asyncio.sleep(0.05)
        self.events.append("playback_done")
        return AudioPlaybackResult(total, first)


class VoicePipelineOverlapTests(unittest.IsolatedAsyncioTestCase):
    async def test_next_phrase_synthesizes_before_prior_audio_playback_finishes(self):
        events = []
        tts = TrackingTTS(events)
        core = ConversationCore(context=ConversationContext("conv", "user"), provider=TwoPhraseIntelligence())
        engine = VoiceLabEngine(
            conversation=core,
            providers=VoiceProviderRegistry(STT(), tts),
            audio_input=Input(),
            audio_output=SlowOutput(events),
            vad=VAD(),
            endpoint_config=EndpointConfig(frame_ms=30, start_trigger_ms=60, end_silence_ms=60, preroll_ms=60),
        )
        result = await engine.run_once()
        self.assertEqual(result.status, "completed")
        self.assertGreaterEqual(tts.calls, 2)
        self.assertLess(events.index("tts2_start"), events.index("playback_done"))


if __name__ == "__main__":
    unittest.main()
