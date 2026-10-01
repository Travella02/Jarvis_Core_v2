import tempfile
import unittest
from pathlib import Path

from core.voice.conversation_control import (
    SleepPhraseDetector,
    WakePhraseDetector,
    WakeSleepConfig,
)


class WakeSleepControlTests(unittest.TestCase):
    def test_full_sentence_wake_strips_only_invocation(self):
        detector = WakePhraseDetector(("hey jarvis", "jarvis"))
        match = detector.match("Hey Jarvis, what are the latest updates in Rocket League?")
        self.assertIsNotNone(match)
        self.assertEqual(match.phrase, "hey jarvis")
        self.assertEqual(match.command_text, "what are the latest updates in Rocket League?")

    def test_custom_wake_phrase_is_provider_neutral(self):
        detector = WakePhraseDetector(("computer",))
        match = detector.match("Computer, turn on the lights")
        self.assertIsNotNone(match)
        self.assertEqual(match.command_text, "turn on the lights")
        self.assertIsNone(detector.match("Jarvis, turn on the lights"))

    def test_wake_phrase_must_lead_utterance(self):
        detector = WakePhraseDetector(("jarvis",))
        self.assertIsNone(detector.match("I was telling Jarvis about that"))

    def test_sleep_phrase_is_exact_command_not_substring(self):
        detector = SleepPhraseDetector(("that's all", "go to sleep jarvis"))
        self.assertTrue(detector.matches("That's all."))
        self.assertTrue(detector.matches("Go to sleep, Jarvis."))
        self.assertFalse(detector.matches("Is that all Jarvis can do?"))

    def test_env_file_can_customize_wake_sleep_and_idle_timeout(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / ".env"
            path.write_text(
                "JARVIS_WAKE_PHRASES=computer|hey computer\n"
                "JARVIS_SLEEP_PHRASES=stand down|good night computer\n"
                "JARVIS_IDLE_SLEEP_SECONDS=75\n",
                encoding="utf-8",
            )
            config = WakeSleepConfig.from_env(env={}, env_file=path)
        self.assertEqual(config.wake_phrases, ("computer", "hey computer"))
        self.assertEqual(config.sleep_phrases, ("stand down", "good night computer"))
        self.assertEqual(config.idle_timeout_seconds, 75.0)


if __name__ == "__main__":
    unittest.main()
