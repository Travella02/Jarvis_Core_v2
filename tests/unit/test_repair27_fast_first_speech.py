import unittest

from core.conversation.engine import VOICE_RESPONSE_INSTRUCTION
from core.voice import SpeechTextChunker


class Repair27FastFirstSpeechTests(unittest.TestCase):
    def test_short_complete_first_sentence_releases_before_old_floor(self):
        chunker = SpeechTextChunker()
        self.assertEqual(chunker.push("Venus spins."), ("Venus spins.",))

    def test_later_chunks_keep_original_minimum_floor(self):
        chunker = SpeechTextChunker()
        self.assertEqual(chunker.push("Venus spins."), ("Venus spins.",))
        self.assertEqual(chunker.push(" It is fast."), ())
        self.assertEqual(chunker.flush(), "It is fast.")

    def test_three_word_opening_comma_clause_can_start_tts(self):
        chunker = SpeechTextChunker()
        self.assertEqual(
            chunker.push("Venus spins slowly, because tides affect it"),
            ("Venus spins slowly.",),
        )
        self.assertEqual(chunker.flush(), "because tides affect it")

    def test_tiny_discourse_opener_still_does_not_split(self):
        chunker = SpeechTextChunker()
        self.assertEqual(chunker.push("Sure, Venus is unusual"), ())

    def test_voice_policy_front_loads_direct_short_sentence(self):
        self.assertIn("target three to six spoken words", VOICE_RESPONSE_INSTRUCTION)
        self.assertIn("sentence-ending punctuation immediately", VOICE_RESPONSE_INSTRUCTION)
        self.assertIn("not be filler", VOICE_RESPONSE_INSTRUCTION)
        self.assertIn("answer the user's intent", VOICE_RESPONSE_INSTRUCTION)


if __name__ == "__main__":
    unittest.main()
