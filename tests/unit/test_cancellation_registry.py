import unittest

from core.common.cancellation import CancellationRegistry
from core.common.ids import CorrelationContext


class CancellationRegistryTests(unittest.TestCase):
    def test_turn_has_targetable_cancellation_id(self) -> None:
        registry = CancellationRegistry()
        trace = CorrelationContext.create()
        handle = registry.register(trace)
        self.assertEqual(handle.cancellation_id, trace.cancellation_id)
        self.assertTrue(registry.cancel(handle.cancellation_id, "stop"))
        self.assertTrue(handle.token.is_cancelled)
        self.assertEqual(handle.token.reason, "stop")

    def test_complete_removes_request_and_cancel_indexes(self) -> None:
        registry = CancellationRegistry()
        trace = CorrelationContext.create()
        handle = registry.register(trace)
        registry.complete(handle.cancellation_id)
        self.assertIsNone(registry.get(handle.cancellation_id))
        self.assertIsNone(registry.get_for_request(trace.request_id))


if __name__ == "__main__":
    unittest.main()
