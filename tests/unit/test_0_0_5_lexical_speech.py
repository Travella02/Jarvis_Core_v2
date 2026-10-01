import unittest

from core.voice.lexical import (
    confirms_early_interruption,
    has_lexical_speech,
    lexical_words,
)


class LexicalSpeechTests(unittest.TestCase):
    def test_words_are_semantic_authority(self):
        self.assertTrue(has_lexical_speech("Why is that?"))
        self.assertTrue(has_lexical_speech("stop"))
        self.assertFalse(has_lexical_speech("... --- !!!"))

    def test_early_probe_accepts_real_followup_words(self):
        self.assertTrue(confirms_early_interruption("Why is that?"))
        self.assertTrue(confirms_early_interruption("Actually"))
        self.assertTrue(confirms_early_interruption("stop"))

    def test_common_silence_hallucinations_do_not_cancel_early(self):
        self.assertFalse(confirms_early_interruption("Thank you."))
        self.assertFalse(confirms_early_interruption("Thanks for watching."))
        self.assertFalse(confirms_early_interruption("you"))

    def test_tokenizer_preserves_contractions(self):
        self.assertEqual(lexical_words("that's all"), ("that's", "all"))


if __name__ == "__main__":
    unittest.main()
