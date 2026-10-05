import asyncio
import unittest

from core.intelligence import (
    ContextLimits,
    IntelligenceEvent,
    IntelligenceEventType,
    IntelligenceProvider,
    ProviderHealth,
    ProviderHealthState,
    ProviderMetadata,
)
from core.runtime import IntelligenceProviderRouter, ProviderRouteError


class FakeProvider(IntelligenceProvider):
    def __init__(self, name="fake", *, tools=False, delay=0.0, fail_health=False):
        self.name = name
        self.tools = tools
        self.delay = delay
        self.fail_health = fail_health

    async def stream_response(self, context, tools, reasoning_policy, cancellation_token):
        yield IntelligenceEvent(IntelligenceEventType.COMPLETED)

    def supports_tools(self):
        return self.tools

    def supports_vision(self):
        return False

    def supports_reasoning_levels(self):
        return True

    def context_limits(self):
        return ContextLimits()

    async def cancel(self, request_id):
        return None

    async def health(self):
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail_health:
            raise RuntimeError("secret provider failure")
        return ProviderHealth(ProviderHealthState.HEALTHY, "ready")

    @property
    def metadata(self):
        return ProviderMetadata(self.name, f"{self.name}-model")


class ProviderRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_route_is_explicit_and_never_silently_falls_back(self) -> None:
        router = IntelligenceProviderRouter(default_route="primary")
        primary = FakeProvider("primary")
        alternate = FakeProvider("alternate")
        router.register("primary", primary)
        router.register("alternate", alternate)
        self.assertIs(router.resolve(), primary)
        with self.assertRaises(ProviderRouteError):
            router.resolve("missing")

    async def test_capability_requirement_rejects_incompatible_route(self) -> None:
        router = IntelligenceProviderRouter()
        router.register("primary", FakeProvider("primary", tools=False), make_default=True)
        with self.assertRaises(ProviderRouteError):
            router.resolve(require_tools=True)

    async def test_health_probe_times_out_without_blocking_other_routes(self) -> None:
        router = IntelligenceProviderRouter()
        router.register("slow", FakeProvider("slow", delay=0.2), make_default=True)
        router.register("fast", FakeProvider("fast"))
        results = await router.health(timeout_seconds=0.02)
        self.assertEqual(results["slow"].state, ProviderHealthState.DEGRADED)
        self.assertEqual(results["fast"].state, ProviderHealthState.HEALTHY)

    async def test_health_exceptions_are_redacted_to_exception_type(self) -> None:
        router = IntelligenceProviderRouter()
        router.register("primary", FakeProvider("primary", fail_health=True), make_default=True)
        results = await router.health(timeout_seconds=0.1)
        self.assertEqual(results["primary"].state, ProviderHealthState.DEGRADED)
        self.assertIn("RuntimeError", results["primary"].detail)
        self.assertNotIn("secret provider failure", results["primary"].detail)


if __name__ == "__main__":
    unittest.main()
