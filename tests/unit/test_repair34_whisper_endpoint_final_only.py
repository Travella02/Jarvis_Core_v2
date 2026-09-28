import asyncio
import unittest

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.voice import AudioFormat, AudioFrame, AudioSampleFormat, TranscriptionEventType
from providers.stt.whisper_cpp import WhisperCppConfig, WhisperCppProvider


class CountingWhisper(WhisperCppProvider):
    def __init__(self, config):
        super().__init__(config)
        self.calls = 0

    async def _ensure_server(self):
        return None

    async def _transcribe(self, frames):
        self.calls += 1
        await asyncio.sleep(0)
        return "hello world"


def config(*, emit_partials):
    base = WhisperCppConfig.from_env({
        "JARVIS_WHISPER_SERVER_EXE": __file__,
        "JARVIS_WHISPER_MODEL": __file__,
    })
    from dataclasses import replace
    return replace(
        base,
        emit_partials=emit_partials,
        min_partial_audio_ms=300,
        partial_interval_ms=300,
    )


async def audio(frames=40):
    trace = CorrelationContext.create()
    fmt = AudioFormat(16_000, 1, AudioSampleFormat.PCM_S16LE)
    payload = b"\x00\x00" * 480  # 30 ms
    for index in range(frames):
        yield AudioFrame(trace=trace, sequence=index, format=fmt, payload=payload)


class Repair34WhisperEndpointFinalOnlyTests(unittest.IsolatedAsyncioTestCase):
    async def test_final_only_runs_exactly_one_full_inference(self):
        provider = CountingWhisper(config(emit_partials=False))
        events = [
            event async for event in provider.stream_transcription(
                audio(), CancellationToken()
            )
        ]
        self.assertEqual(provider.calls, 1)
        self.assertEqual(
            [event.event_type for event in events],
            [TranscriptionEventType.FINAL],
        )
        self.assertEqual(events[0].text, "hello world")

    async def test_control_mode_still_runs_partial_then_final(self):
        provider = CountingWhisper(config(emit_partials=True))
        events = [
            event async for event in provider.stream_transcription(
                audio(), CancellationToken()
            )
        ]
        self.assertGreaterEqual(provider.calls, 2)
        self.assertIn(
            TranscriptionEventType.PARTIAL,
            [event.event_type for event in events],
        )
        self.assertEqual(events[-1].event_type, TranscriptionEventType.FINAL)

    async def test_final_only_uses_same_complete_audio_for_final(self):
        seen = []

        class RecordingWhisper(CountingWhisper):
            async def _transcribe(self, frames):
                self.calls += 1
                seen.append(len(frames))
                return "same full utterance"

        provider = RecordingWhisper(config(emit_partials=False))
        events = [
            event async for event in provider.stream_transcription(
                audio(frames=37), CancellationToken()
            )
        ]
        self.assertEqual(seen, [37])
        self.assertEqual(events[-1].text, "same full utterance")

    def test_metadata_reports_selected_mode(self):
        final_only = CountingWhisper(config(emit_partials=False))
        control = CountingWhisper(config(emit_partials=True))
        self.assertTrue(final_only.metadata.extra["endpointed_final_only"])
        self.assertFalse(final_only.metadata.extra["partials"])
        self.assertFalse(control.metadata.extra["endpointed_final_only"])
        self.assertTrue(control.metadata.extra["partials"])


if __name__ == "__main__":
    unittest.main()
