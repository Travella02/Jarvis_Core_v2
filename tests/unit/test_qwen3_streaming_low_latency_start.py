import unittest

from providers.tts.qwen3_streaming_candidate import Qwen3StreamingConfig, Qwen3StreamingProvider


class Qwen3StreamingLowLatencyStartTests(unittest.TestCase):
    def test_startup_runway_releases_on_first_normal_streaming_chunk(self):
        cfg = Qwen3StreamingConfig()
        # Repair23 measured normal emitted chunks at about 319-320 ms.
        # Keep the runway below one normal chunk so playback can start on
        # the first generated PCM frame instead of waiting for a second.
        self.assertGreater(cfg.startup_buffer_ms, 0)
        self.assertLess(cfg.startup_buffer_ms, 300)

    def test_provider_advertises_fast_start_strategy(self):
        provider = Qwen3StreamingProvider()
        self.assertEqual(
            provider.metadata.extra["startup_buffer_strategy"],
            "single-frame-fast-start",
        )


if __name__ == "__main__":
    unittest.main()
