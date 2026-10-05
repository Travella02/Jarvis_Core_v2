import unittest

from core.runtime import (
    ComponentHealthState,
    HealthRegistry,
    RuntimeHealthState,
)


class RuntimeHealthTests(unittest.TestCase):
    def test_health_axes_do_not_mutate_runtime_or_conversation_state(self) -> None:
        registry = HealthRegistry()
        registry.update("runtime", ComponentHealthState.HEALTHY, critical=True)
        self.assertEqual(registry.snapshot().state, RuntimeHealthState.HEALTHY)
        registry.update("optional-tts", ComponentHealthState.DEGRADED, critical=False)
        self.assertEqual(registry.snapshot().state, RuntimeHealthState.DEGRADED)

    def test_critical_unavailable_component_is_error(self) -> None:
        registry = HealthRegistry()
        registry.update("runtime", ComponentHealthState.HEALTHY, critical=True)
        registry.update("intelligence:primary", ComponentHealthState.UNAVAILABLE, critical=True)
        self.assertEqual(registry.snapshot().state, RuntimeHealthState.ERROR)


if __name__ == "__main__":
    unittest.main()
