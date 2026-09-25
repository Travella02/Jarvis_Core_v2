import unittest

from core.common.ids import CorrelationContext
from core.voice import AudioFormat, AudioFrame, AudioSampleFormat
from integrations.audio.sounddevice_io import _resample_output_frame_to_rate


class VoiceAudioTests(unittest.TestCase):
    def test_pcm16_frame_duration(self):
        frame = AudioFrame(
            trace=CorrelationContext.create(),
            sequence=0,
            format=AudioFormat(16000, 1, AudioSampleFormat.PCM_S16LE),
            payload=b"\x00\x00" * 480,
        )
        self.assertAlmostEqual(frame.duration_ms, 30.0)


    def test_output_resampling_preserves_frame_duration(self):
        frame = AudioFrame(
            trace=CorrelationContext.create(),
            sequence=0,
            format=AudioFormat(24000, 1, AudioSampleFormat.PCM_S16LE),
            payload=b"\x10\x00" * 720,
        )
        payload, fmt = _resample_output_frame_to_rate(frame, 44100)
        converted = AudioFrame(
            trace=frame.trace, sequence=0, format=fmt, payload=payload
        )
        self.assertEqual(fmt.sample_rate_hz, 44100)
        self.assertAlmostEqual(converted.duration_ms, 30.0, places=1)

    def test_audio_format_rejects_invalid_shape(self):
        with self.assertRaises(ValueError):
            AudioFormat(0)
        with self.assertRaises(ValueError):
            AudioFormat(16000, 0)
