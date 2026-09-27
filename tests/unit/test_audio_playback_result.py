import unittest
from core.voice.audio import AudioPlaybackResult

class AudioPlaybackResultTests(unittest.TestCase):
    def test_repair26_accepts_detailed_playback_timing(self):
        result = AudioPlaybackResult(
            100,
            first_write_monotonic_ns=1_000,
            first_write_completed_monotonic_ns=2_000,
            estimated_first_audible_monotonic_ns=1_200,
            output_latency_ms=0.2,
            low_latency_requested=True,
            low_latency_active=True,
        )
        self.assertEqual(result.first_write_monotonic_ns, 1_000)
        self.assertEqual(result.first_write_completed_monotonic_ns, 2_000)
        self.assertEqual(result.estimated_first_audible_monotonic_ns, 1_200)
        self.assertTrue(result.low_latency_active)

    def test_negative_output_latency_is_rejected(self):
        with self.assertRaises(ValueError):
            AudioPlaybackResult(0, output_latency_ms=-1)

if __name__ == "__main__":
    unittest.main()
