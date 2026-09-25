import unittest

from core.voice import normalize_speech_text


class VoiceSpeechNormalizationTests(unittest.TestCase):
    def test_removes_display_markdown_without_changing_words(self):
        self.assertEqual(
            normalize_speech_text("**243 Earth days** and [Venus](https://example.com)."),
            "243 Earth days and Venus.",
        )

    def test_removes_headings_bullets_and_code_ticks(self):
        self.assertEqual(normalize_speech_text("# Fact\n- `Venus` spins slowly."), "Fact Venus spins slowly.")

    def test_empty_display_artifacts_do_not_become_speech(self):
        self.assertEqual(normalize_speech_text("***"), "")


if __name__ == "__main__":
    unittest.main()
