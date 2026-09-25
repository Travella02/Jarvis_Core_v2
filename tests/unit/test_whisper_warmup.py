import unittest

from providers.stt.whisper_cpp import WhisperCppProvider


class WhisperWarmupTests(unittest.IsolatedAsyncioTestCase):
    async def test_warmup_builds_hidden_frame_without_runtime_name_error(self):
        provider = WhisperCppProvider()
        seen = {}

        async def fake_ensure_server():
            return None

        async def fake_transcribe(frames):
            seen["frames"] = frames
            return ""

        provider._ensure_server = fake_ensure_server  # type: ignore[method-assign]
        provider._transcribe = fake_transcribe  # type: ignore[method-assign]

        await provider.warmup()

        frames = seen["frames"]
        self.assertEqual(len(frames), 1)
        frame = frames[0]
        self.assertEqual(frame.format.sample_rate_hz, 16000)
        self.assertEqual(frame.format.channels, 1)
        self.assertEqual(len(frame.payload), 32000)
        self.assertTrue(frame.trace.correlation_id)
        self.assertTrue(frame.trace.request_id)


if __name__ == "__main__":
    unittest.main()
