import unittest

from core.voice.lexical import (
    TranscriptEvidenceTracker,
    has_lexical_speech,
    lexical_words,
    transcript_compatible,
)


class LexicalSpeechTests(unittest.TestCase):
    def test_one_word_and_multiword_transcripts_are_both_lexical(self):
        self.assertTrue(has_lexical_speech("Yes."))
        self.assertTrue(has_lexical_speech("Why is that?"))
        self.assertTrue(has_lexical_speech("stop"))
        self.assertFalse(has_lexical_speech("... --- !!!"))

    def test_no_keyword_specific_early_interruption_policy_remains(self):
        import core.voice.lexical as lexical

        self.assertFalse(hasattr(lexical, "_EARLY_SINGLE_WORDS"))
        self.assertFalse(hasattr(lexical, "_EARLY_HALLUCINATION_PHRASES"))
        self.assertFalse(hasattr(lexical, "confirms_early_interruption"))

    def test_stability_is_generic_and_not_word_specific(self):
        tracker = TranscriptEvidenceTracker()
        self.assertEqual(tracker.stability_score("yes"), 0.0)
        tracker.observe_partial("yes")
        self.assertGreater(tracker.stability_score("yes"), 0.9)

        tracker2 = TranscriptEvidenceTracker()
        tracker2.observe_partial("tell me")
        self.assertGreater(tracker2.stability_score("tell me about mars"), 0.5)

    def test_compatibility_handles_short_answers_without_special_cases(self):
        self.assertTrue(transcript_compatible("yes", "yes"))
        self.assertFalse(transcript_compatible("yes", "you"))

    def test_tokenizer_preserves_contractions(self):
        self.assertEqual(lexical_words("that's all"), ("that's", "all"))


if __name__ == "__main__":
    unittest.main()
