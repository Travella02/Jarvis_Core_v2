import unittest

from core.voice import SpeechTextChunker


class VoiceChunkingTests(unittest.TestCase):
    def test_prefers_natural_sentence_boundary(self):
        chunker = SpeechTextChunker(min_chars=8, soft_max_chars=40, hard_max_chars=100)
        chunks = chunker.push("Hello there. This is a second phrase.")
        self.assertEqual(chunks, ("Hello there.", "This is a second phrase."))
        self.assertIsNone(chunker.flush())

    def test_does_not_force_mid_sentence_cut_at_soft_limit(self):
        chunker = SpeechTextChunker(min_chars=5, soft_max_chars=10, hard_max_chars=40, clause_min_chars=8)
        self.assertEqual(chunker.push("one two three four"), ())
        self.assertEqual(chunker.flush(), "one two three four")

    def test_hard_limit_still_bounds_unpunctuated_run_on_text(self):
        chunker = SpeechTextChunker(min_chars=5, soft_max_chars=10, hard_max_chars=18, clause_min_chars=8)
        chunks = chunker.push("one two three four five six")
        self.assertTrue(chunks)
        self.assertLessEqual(len(chunks[0]), 18)

    def test_first_useful_comma_clause_can_become_complete_spoken_unit(self):
        chunker = SpeechTextChunker()
        self.assertEqual(
            chunker.push("Venus rotates extremely slowly, likely because gravitational tides"),
            ("Venus rotates extremely slowly.",),
        )
        self.assertEqual(chunker.flush(), "likely because gravitational tides")

    def test_tiny_discourse_opener_is_not_split_at_comma(self):
        chunker = SpeechTextChunker()
        self.assertEqual(chunker.push("Well, that is an interesting question"), ())

    def test_example_venus_sentence_is_not_split_before_year(self):
        chunker = SpeechTextChunker()
        self.assertEqual(chunker.push("A day on Venus is longer than its"), ())
        self.assertEqual(
            chunker.push(" year. Venus takes about 243 Earth days."),
            ("A day on Venus is longer than its year.", "Venus takes about 243 Earth days."),
        )


if __name__ == "__main__":
    unittest.main()
