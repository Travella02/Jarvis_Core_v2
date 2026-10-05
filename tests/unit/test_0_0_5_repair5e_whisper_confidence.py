import math
import unittest

from providers.stt.whisper_cpp.provider import WhisperCppProvider


class Repair5eWhisperConfidenceTests(unittest.TestCase):
    def test_verbose_json_prefers_word_probabilities(self):
        payload = {
            "text": "yes",
            "segments": [
                {
                    "words": [
                        {"word": " yes", "probability": 0.92},
                    ],
                    "tokens": [
                        {"text": " yes", "probability": 0.20},
                    ],
                    "no_speech_prob": 0.04,
                }
            ],
        }
        confidence, no_speech = WhisperCppProvider._confidence_from_verbose_json(payload)
        self.assertIsNotNone(confidence)
        self.assertGreater(confidence, 0.85)
        self.assertAlmostEqual(no_speech, 0.04)

    def test_avg_logprob_is_used_when_probabilities_are_absent(self):
        payload = {
            "text": "hello",
            "segments": [{"avg_logprob": math.log(0.8), "no_speech_prob": 0.0}],
        }
        confidence, _ = WhisperCppProvider._confidence_from_verbose_json(payload)
        self.assertIsNotNone(confidence)
        self.assertAlmostEqual(confidence, 0.8, places=3)

    def test_missing_metadata_is_allowed(self):
        confidence, no_speech = WhisperCppProvider._confidence_from_verbose_json(
            {"text": "hello"}
        )
        self.assertIsNone(confidence)
        self.assertIsNone(no_speech)

    def test_provider_requests_verbose_json_without_second_inference(self):
        from pathlib import Path

        text = (
            Path(__file__).resolve().parents[2]
            / "providers/stt/whisper_cpp/provider.py"
        ).read_text(encoding="utf-8")
        self.assertIn('field("response_format", "verbose_json")', text)
        self.assertIn("self._last_inference = inference", text)
        self.assertNotIn("confidence probe", text.lower())


if __name__ == "__main__":
    unittest.main()
