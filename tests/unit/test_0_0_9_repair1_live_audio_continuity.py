from __future__ import annotations

import asyncio
import math
import unittest
from array import array

from integrations.audio.sounddevice_io import _StreamingPCM16MonoResampler
from integrations.audio.streaming_pcm import StreamingPCM16PlaybackBuffer
from providers.voice_frontend.openai_live.config import OpenAIGPTLiveConfig


def pcm16(values: list[int]) -> bytes:
    samples = array("h", values)
    return samples.tobytes()


def sine_pcm(sample_rate: int, duration_ms: int, hz: float = 440.0) -> bytes:
    count = round(sample_rate * duration_ms / 1000)
    values = [round(math.sin(2.0 * math.pi * hz * i / sample_rate) * 12000) for i in range(count)]
    return pcm16(values)


class LiveAudioContinuityTests(unittest.IsolatedAsyncioTestCase):
    def test_gpt_live_defaults_to_24khz_pcm(self) -> None:
        cfg = OpenAIGPTLiveConfig.from_env({"OPENAI_API_KEY": "test"})
        self.assertEqual(cfg.audio_rate_hz, 24000)

    def test_streaming_resampler_is_independent_of_network_packet_boundaries(self) -> None:
        source = sine_pcm(24000, 160)

        whole = _StreamingPCM16MonoResampler(24000, 44100)
        expected = whole.process(source) + whole.flush()

        split = _StreamingPCM16MonoResampler(24000, 44100)
        chunks = [source[:718], source[718:2118], source[2118:4140], source[4140:]]
        actual = b"".join(split.process(chunk) for chunk in chunks) + split.flush()

        self.assertEqual(actual, expected)
        self.assertGreater(len(actual), len(source))

    async def test_playback_buffer_reframes_arbitrary_chunks_and_prebuffers_two_frames(self) -> None:
        buffer = StreamingPCM16PlaybackBuffer(
            sample_rate_hz=24000,
            frame_ms=20,
            prebuffer_ms=40,
            fade_ms=5,
        )
        # 40 ms total, deliberately split at odd network-frame boundaries while
        # keeping each PCM payload sample-aligned.
        source = sine_pcm(24000, 40)
        buffer.append(source[:314])
        buffer.append(source[314:1000])
        buffer.append(source[1000:])
        buffer.close()

        frames = [frame async for frame in buffer.frames()]
        self.assertEqual(len(frames), 2)
        self.assertTrue(all(len(frame) == 960 for frame in frames))

    async def test_interrupt_discards_queued_pcm_and_emits_short_fade_to_zero(self) -> None:
        buffer = StreamingPCM16PlaybackBuffer(
            sample_rate_hz=24000,
            frame_ms=20,
            prebuffer_ms=20,
            fade_ms=5,
        )
        # Prime one frame so the buffer knows the last delivered waveform sample.
        buffer.append(pcm16([10000] * 480))
        iterator = buffer.frames().__aiter__()
        first = await asyncio.wait_for(anext(iterator), timeout=1)
        self.assertEqual(len(first), 960)

        # Queue audio that should never be heard, then interrupt before consuming it.
        buffer.append(pcm16([20000] * 960))
        buffer.interrupt()
        fade = await asyncio.wait_for(anext(iterator), timeout=1)
        fade_samples = array("h")
        fade_samples.frombytes(fade)
        self.assertEqual(len(fade_samples), 480)
        self.assertEqual(fade_samples[-1], 0)
        self.assertLess(abs(fade_samples[119]), abs(fade_samples[0]))
        self.assertGreater(buffer.stats.dropped_bytes, 0)
        self.assertEqual(buffer.stats.interruptions, 1)
        buffer.close()


if __name__ == "__main__":
    unittest.main()
