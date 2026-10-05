import unittest

from core.voice.confidence import SpeechConfidenceConfig, SpeechConfidenceValidator
from core.voice.lexical import TranscriptEvidenceTracker


class Repair5eSpeechConfidenceTests(unittest.TestCase):
    def setUp(self):
        self.validator = SpeechConfidenceValidator()

    def test_high_confidence_one_word_answer_is_accepted(self):
        tracker = TranscriptEvidenceTracker()
        tracker.observe_partial("yes")
        decision = self.validator.evaluate(
            stage="final",
            transcript="Yes.",
            vad_probabilities=(0.91, 0.94, 0.90, 0.88),
            asr_confidence=0.92,
            tracker=tracker,
            duration_ms=420,
        )
        self.assertTrue(decision.accepted)
        self.assertGreaterEqual(decision.score, decision.threshold)

    def test_noise_like_one_word_hallucination_is_rejected_without_word_blacklist(self):
        tracker = TranscriptEvidenceTracker()
        decision = self.validator.evaluate(
            stage="final",
            transcript="you",
            vad_probabilities=(0.58, 0.64, 0.55),
            asr_confidence=0.24,
            tracker=tracker,
            duration_ms=180,
        )
        self.assertFalse(decision.accepted)
        self.assertLess(decision.score, decision.threshold)

    def test_same_signals_score_same_regardless_of_word_meaning(self):
        kwargs = dict(
            stage="partial",
            vad_probabilities=(0.93, 0.92, 0.89),
            asr_confidence=0.91,
            duration_ms=390,
        )
        a_tracker = TranscriptEvidenceTracker()
        b_tracker = TranscriptEvidenceTracker()
        a = self.validator.evaluate(transcript="stop", tracker=a_tracker, **kwargs)
        b = self.validator.evaluate(transcript="blue", tracker=b_tracker, **kwargs)
        self.assertAlmostEqual(a.score, b.score)
        self.assertEqual(a.accepted, b.accepted)

    def test_early_interruption_requires_stronger_score_than_final_acceptance(self):
        config = SpeechConfidenceConfig()
        self.assertGreater(config.early_accept_threshold, config.final_accept_threshold)

    def test_missing_asr_confidence_redistributes_weight_instead_of_rejecting_one_word(self):
        tracker = TranscriptEvidenceTracker()
        tracker.observe_partial("yes")
        decision = self.validator.evaluate(
            stage="final",
            transcript="yes",
            vad_probabilities=(0.96, 0.95, 0.93, 0.92),
            asr_confidence=None,
            tracker=tracker,
            duration_ms=500,
        )
        self.assertTrue(decision.accepted)

    def test_first_partial_can_remain_provisional_until_more_evidence_arrives(self):
        tracker = TranscriptEvidenceTracker()
        weak = self.validator.evaluate(
            stage="partial",
            transcript="maybe",
            vad_probabilities=(0.62, 0.58),
            asr_confidence=0.45,
            tracker=tracker,
            duration_ms=220,
        )
        self.assertFalse(weak.accepted)

        tracker.observe_partial("maybe")
        strong = self.validator.evaluate(
            stage="partial",
            transcript="maybe",
            vad_probabilities=(0.88, 0.90, 0.91, 0.89),
            asr_confidence=0.88,
            tracker=tracker,
            duration_ms=480,
        )
        self.assertTrue(strong.accepted)


if __name__ == "__main__":
    unittest.main()
