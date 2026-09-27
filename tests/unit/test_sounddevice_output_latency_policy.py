import unittest
from integrations.audio.sounddevice_io import (
    _open_output_stream_low_latency_first,
    _output_latency_seconds,
)

class _Stream:
    def __init__(self, latency=0.025):
        self.latency = latency

class _LowWorks:
    def __init__(self):
        self.calls = []
    def RawOutputStream(self, **kwargs):
        self.calls.append(dict(kwargs))
        return _Stream()

class _LowFails:
    def __init__(self):
        self.calls = []
    def RawOutputStream(self, **kwargs):
        self.calls.append(dict(kwargs))
        if kwargs.get("latency") == "low":
            raise RuntimeError("backend rejected low latency")
        return _Stream()

class SoundDeviceOutputLatencyPolicyTests(unittest.TestCase):
    def test_requests_low_latency_first(self):
        sd = _LowWorks()
        stream, active = _open_output_stream_low_latency_first(
            sd, samplerate=44100, channels=1, dtype="int16", device=4
        )
        self.assertTrue(active)
        self.assertEqual(sd.calls[0]["latency"], "low")
        self.assertAlmostEqual(_output_latency_seconds(stream), 0.025)

    def test_falls_back_if_backend_rejects_low_latency(self):
        sd = _LowFails()
        _stream, active = _open_output_stream_low_latency_first(
            sd, samplerate=44100, channels=1, dtype="int16", device=4
        )
        self.assertFalse(active)
        self.assertEqual(len(sd.calls), 2)
        self.assertNotIn("latency", sd.calls[1])

    def test_tuple_latency_uses_output_side(self):
        self.assertAlmostEqual(_output_latency_seconds(_Stream((0.01, 0.02))), 0.02)

if __name__ == "__main__":
    unittest.main()
