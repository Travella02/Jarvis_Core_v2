import unittest
from unittest.mock import patch

from core.voice import AudioFormat, AudioSampleFormat
from integrations.audio import sounddevice_io
from tests.unit.test_sounddevice_native_rate import _FakeSD


class AudioDiagnosticCaptureTests(unittest.IsolatedAsyncioTestCase):
    async def test_diagnostic_capture_preserves_raw_native_and_exact_16k_frames(self):
        fake = _FakeSD()
        source = sounddevice_io.SoundDeviceAudioInput(17)
        with patch.object(sounddevice_io, "_sounddevice", return_value=fake):
            result = await source.capture_diagnostic(
                duration_s=0.06,
                audio_format=AudioFormat(16000, 1, AudioSampleFormat.PCM_S16LE),
                frame_ms=30,
            )

        self.assertEqual(result.native_sample_rate_hz, 48000)
        self.assertEqual(len(result.raw_native_pcm16), 2 * 1440 * 2)
        self.assertEqual(len(result.processed_frames), 2)
        self.assertTrue(all(len(frame.payload) == 480 * 2 for frame in result.processed_frames))


if __name__ == "__main__":
    unittest.main()
