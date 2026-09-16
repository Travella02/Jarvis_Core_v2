import unittest

from core.conversation import run_conversation_benchmark


class ConversationReferentRegressionTests(unittest.TestCase):
    def test_conversation_core_seed_benchmark_passes(self) -> None:
        results = run_conversation_benchmark()
        failures = [item for item in results if not item.passed]
        self.assertEqual(failures, [])
        self.assertEqual(len(results), 6)


if __name__ == "__main__":
    unittest.main()
