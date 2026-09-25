import asyncio
import unittest
from unittest.mock import patch

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.voice import AudioFormat, AudioSampleFormat
from integrations.audio import sounddevice_io


class _FakeRawInputStream:
    def __init__(self, owner, **kwargs):
        self.owner = owner
        self.kwargs = kwargs
        owner.open_kwargs = kwargs
        self.started = False
        self.closed = False

    def start(self):
        self.started = True

    def read(self, frames):
        self.owner.read_frames.append(frames)
        # deterministic ramp at the native device rate
        values = bytearray()
        for index in range(frames):
            sample = min(32767, index * 10)
            values += int(sample).to_bytes(2, "little", signed=True)
        return bytes(values), False

    def stop(self):
        self.started = False

    def close(self):
        self.closed = True


class _FakeSD:
    def __init__(self):
        self.default = type("Default", (), {"device": (17, 4)})()
        self.open_kwargs = None
        self.read_frames = []
        self.checked = []
        self._devices = [
            {
                "name": "unused",
                "max_input_channels": 0,
                "max_output_channels": 0,
                "default_samplerate": 44100.0,
                "hostapi": 0,
            }
            for _ in range(18)
        ]
        self._devices[17] = {
            "name": "Microphone (HyperX Cloud Alpha Wireless)",
            "max_input_channels": 1,
            "max_output_channels": 0,
            "default_samplerate": 48000.0,
            "hostapi": 1,
        }

    def query_devices(self, index=None):
        return self._devices if index is None else self._devices[index]

    def query_hostapis(self):
        return [{"name": "MME"}, {"name": "Windows WASAPI"}]

    def check_input_settings(self, **kwargs):
        self.checked.append(kwargs)

    def RawInputStream(self, **kwargs):
        return _FakeRawInputStream(self, **kwargs)


class SoundDeviceNativeRateTests(unittest.IsolatedAsyncioTestCase):
    async def test_selected_microphone_opens_at_native_rate_and_emits_16k_frames(self):
        fake = _FakeSD()
        source = sounddevice_io.SoundDeviceAudioInput(17)
        token = CancellationToken()
        trace = CorrelationContext.create()

        with patch.object(sounddevice_io, "_sounddevice", return_value=fake):
            info = await source.selected_device()
            self.assertEqual(info.device_id, "17")
            self.assertEqual(info.default_sample_rate_hz, 48000)
            self.assertEqual(info.host_api, "Windows WASAPI")

            stream = source.stream(
                trace=trace,
                audio_format=AudioFormat(16000, 1, AudioSampleFormat.PCM_S16LE),
                frame_ms=30,
                cancellation_token=token,
            )
            frame = await anext(stream)
            token.cancel("test complete")
            await stream.aclose()

        self.assertEqual(fake.open_kwargs["samplerate"], 48000)
        self.assertEqual(fake.open_kwargs["device"], 17)
        self.assertEqual(fake.open_kwargs["blocksize"], 1440)
        self.assertEqual(fake.read_frames, [1440])
        self.assertEqual(frame.format.sample_rate_hz, 16000)
        self.assertEqual(len(frame.payload), 480 * 2)
        self.assertAlmostEqual(frame.duration_ms, 30.0)

    def test_resampler_produces_exact_requested_sample_count(self):
        source = b"".join(int(i * 100).to_bytes(2, "little", signed=True) for i in range(100))
        output = sounddevice_io._resample_pcm16_mono(source, 40)
        self.assertEqual(len(output), 80)
        self.assertEqual(int.from_bytes(output[:2], "little", signed=True), 0)
        self.assertEqual(int.from_bytes(output[-2:], "little", signed=True), 9900)


if __name__ == "__main__":
    unittest.main()
