import inspect
import unittest

import apps.voice_lab as voice_lab


class VoiceLabRuntimeWiringTests(unittest.TestCase):
    def test_voice_lab_builds_conversation_through_runtime_host(self) -> None:
        source = inspect.getsource(voice_lab.build_engine)
        self.assertIn("JarvisRuntime", source)
        self.assertIn("runtime.create_conversation", source)
        self.assertIn("engine.runtime = runtime", source)

    def test_voice_lab_cleanup_closes_runtime(self) -> None:
        source = inspect.getsource(voice_lab.run_session)
        self.assertIn("runtime.close()", source)


if __name__ == "__main__":
    unittest.main()
