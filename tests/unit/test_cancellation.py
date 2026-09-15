import unittest

from core.common.cancellation import CancellationToken, OperationCancelled


class CancellationTokenTests(unittest.TestCase):
    def test_cancel_is_monotonic_and_preserves_first_reason(self) -> None:
        token = CancellationToken()
        self.assertFalse(token.is_cancelled)
        token.cancel("barge-in")
        token.cancel("second reason")
        self.assertTrue(token.is_cancelled)
        self.assertEqual(token.reason, "barge-in")
        with self.assertRaises(OperationCancelled):
            token.raise_if_cancelled()


if __name__ == "__main__":
    unittest.main()
