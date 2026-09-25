import asyncio
import unittest
from time import monotonic_ns
from collections.abc import AsyncIterator

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
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


class FakeIntelligence(IntelligenceProvider):
    @property
    def metadata(self):
        return ProviderMetadata("fake", "fake")

    def supports_tools(self): return False
    def supports_vision(self): return False
    def supports_reasoning_levels(self): return True
    def context_limits(self): return ContextLimits(1000, 1000)
    async def health(self): return ProviderHealth(ProviderHealthState.HEALTHY)
    async def cancel(self, request_id): return None

    async def stream_response(self, context, tools, reasoning_policy, cancellation_token):
        yield IntelligenceEvent(IntelligenceEventType.TEXT_DELTA, text_delta="Hello there. ")
        await asyncio.sleep(0)
        yield IntelligenceEvent(IntelligenceEventType.TEXT_DELTA, text_delta="Voice path works.")
        yield IntelligenceEvent(IntelligenceEventType.COMPLETED)


class FakeInput(AudioInput):
    async def devices(self):
        return (AudioDeviceInfo("0", "fake", 1, 0, 16000),)

    async def stream(self, *, trace, audio_format, frame_ms, cancellation_token):
        # Two speech frames start the turn, two more speech frames carry content,
        # then two silent frames endpoint it for the test config below.
        values = [True, True, True, True, True, True, True, True, False, False]
        samples = int(audio_format.sample_rate_hz * frame_ms / 1000)
        for seq, speech in enumerate(values):
            sample = 10000 if speech else 0
            payload = int(sample).to_bytes(2, "little", signed=True) * samples
            yield AudioFrame(trace, seq, audio_format, payload)
            await asyncio.sleep(0)


class MarkerVAD(VoiceActivityDetector):
    def is_speech(self, frame):
        return int.from_bytes(frame.payload[:2], "little", signed=True) != 0


class BlindVAD(VoiceActivityDetector):
    def is_speech(self, frame):
        return False


class FalseThenRealInput(AudioInput):
    async def devices(self):
        return (AudioDeviceInfo("0", "fake", 1, 0, 16000),)

    async def stream(self, *, trace, audio_format, frame_ms, cancellation_token):
        samples = int(audio_format.sample_rate_hz * frame_ms / 1000)
        # First candidate: two tiny VAD-positive frames then endpointing silence.
        sequence = 0
        for speech, amplitude in [
            (True, 300), (True, 350), (False, 100), (False, 100),
            (True, 10000), (True, 10000), (True, 10000), (True, 10000),
            (True, 10000), (True, 10000), (True, 10000), (True, 10000),
            (False, 0), (False, 0),
        ]:
            payload = int(amplitude).to_bytes(2, "little", signed=True) * samples
            yield AudioFrame(trace, sequence, audio_format, payload)
            sequence += 1
            await asyncio.sleep(0)


class ThresholdVAD(VoiceActivityDetector):
    def is_speech(self, frame):
        return abs(int.from_bytes(frame.payload[:2], "little", signed=True)) >= 250


class FakeSTT(SpeechToTextProvider):
    def __init__(self): self.call_count = 0
    @property
    def metadata(self): return SpeechProviderMetadata("fake-stt", "fake", True, True, True)
    async def health(self): return SpeechProviderHealth("ready")
    async def cancel(self, request_id): return None

    async def stream_transcription(self, audio, cancellation_token):
        self.call_count += 1
        frames = []
        async for frame in audio:
            frames.append(frame)
            if len(frames) == 2:
                yield TranscriptionEvent(frame.trace, TranscriptionEventType.PARTIAL, "hello")
        self.last_frame_count = len(frames)
        yield TranscriptionEvent(frames[0].trace, TranscriptionEventType.FINAL, "hello jarvis")


class FakeTTS(TextToSpeechProvider):
    def __init__(self): self.texts = []
    @property
    def metadata(self): return SpeechProviderMetadata("fake-tts", "fake", True, False, True)
    async def health(self): return SpeechProviderHealth("ready")
    async def cancel(self, request_id): return None

    async def stream_speech(self, trace, text, voice, cancellation_token):
        self.texts.append(text)
        payload = (text + " ").encode()
        yield AudioFrame(trace, 0, AudioFormat(24000), payload)


class FakeOutput(AudioOutput):
    def __init__(self): self.stopped = False
    async def devices(self): return (AudioDeviceInfo("0", "fake", 0, 1, 24000),)
    async def play(self, audio: AsyncIterator[AudioFrame], cancellation_token: CancellationToken):
        total = 0
        async for frame in audio:
            if cancellation_token.is_cancelled:
                break
            total += len(frame.payload)
        return AudioPlaybackResult(total, monotonic_ns() if total else None)
    async def stop(self): self.stopped = True


class VoiceLabEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_turn_flows_stt_to_shared_conversation_to_tts(self):
        stt, tts, output = FakeSTT(), FakeTTS(), FakeOutput()
        core = ConversationCore(
            context=ConversationContext("conv", "user"),
            provider=FakeIntelligence(),
        )
        engine = VoiceLabEngine(
            conversation=core,
            providers=VoiceProviderRegistry(stt, tts),
            audio_input=FakeInput(),
            audio_output=output,
            vad=MarkerVAD(),
            endpoint_config=EndpointConfig(
                frame_ms=30,
                start_trigger_ms=60,
                end_silence_ms=60,
                preroll_ms=60,
            ),
        )
        result = await engine.run_once()
        self.assertEqual(result.transcript, "hello jarvis")
        self.assertEqual(result.response_text, "Hello there. Voice path works.")
        self.assertEqual(result.status, "completed")
        self.assertEqual(core.context.recent_transcript[0].channel.value, "voice")
        self.assertGreaterEqual(stt.last_frame_count, 8)  # pre-roll preserved
        self.assertEqual(" ".join(part.strip() for part in tts.texts), "Hello there. Voice path works.")
        self.assertEqual(result.playback.unheard_bytes, 0)
        self.assertIn("speech_started", result.latency_ms)
        self.assertIn("stt_final", result.latency_ms)
        self.assertIn("luna_first_text", result.latency_ms)
        self.assertIn("audio_first_played", result.latency_ms)

    async def test_high_energy_speech_can_rescue_blind_vad(self):
        stt = FakeSTT()
        core = ConversationCore(context=ConversationContext("conv", "user"), provider=FakeIntelligence())
        engine = VoiceLabEngine(
            conversation=core,
            providers=VoiceProviderRegistry(stt, FakeTTS()),
            audio_input=FakeInput(),
            audio_output=FakeOutput(),
            vad=BlindVAD(),
            endpoint_config=EndpointConfig(
                frame_ms=30,
                start_trigger_ms=60,
                end_silence_ms=60,
                preroll_ms=60,
            ),
        )
        transcript, _latency, _trace = await engine.listen_once()
        self.assertEqual(transcript, "hello jarvis")
        self.assertEqual(stt.call_count, 1)

    async def test_false_speech_candidate_is_discarded_before_stt_and_listening_continues(self):
        stt = FakeSTT()
        core = ConversationCore(context=ConversationContext("conv", "user"), provider=FakeIntelligence())
        engine = VoiceLabEngine(
            conversation=core,
            providers=VoiceProviderRegistry(stt, FakeTTS()),
            audio_input=FalseThenRealInput(),
            audio_output=FakeOutput(),
            vad=ThresholdVAD(),
            endpoint_config=EndpointConfig(
                frame_ms=30,
                start_trigger_ms=60,
                end_silence_ms=60,
                preroll_ms=60,
            ),
        )
        transcript, _latency, _trace = await engine.listen_once()
        self.assertEqual(transcript, "hello jarvis")
        self.assertEqual(stt.call_count, 1)

    async def test_interrupt_skeleton_stops_output_without_vendor_knowledge(self):
        output = FakeOutput()
        core = ConversationCore(context=ConversationContext("conv", "user"), provider=FakeIntelligence())
        engine = VoiceLabEngine(
            conversation=core,
            providers=VoiceProviderRegistry(FakeSTT(), FakeTTS()),
            audio_input=FakeInput(),
            audio_output=output,
            vad=MarkerVAD(),
        )
        self.assertFalse(await engine.interrupt())
        self.assertTrue(output.stopped)


if __name__ == "__main__":
    unittest.main()
