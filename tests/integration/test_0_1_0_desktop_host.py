import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from apps.desktop_alpha import DesktopRealtimeSession, create_desktop_app
from core.intelligence import (
    ContextLimits,
    IntelligenceEvent,
    IntelligenceEventType,
    IntelligenceProvider,
    ProviderHealth,
    ProviderHealthState,
    ProviderMetadata,
)
from core.runtime import IntelligenceProviderRouter, JarvisRuntime, RuntimeSettings
from providers.voice_frontend.openai_realtime import OpenAIRealtimeConfig


class FakeProvider(IntelligenceProvider):
    async def stream_response(self, context, tools, reasoning_policy, cancellation_token):
        yield IntelligenceEvent(IntelligenceEventType.TEXT_DELTA, text_delta="backend result")
        yield IntelligenceEvent(IntelligenceEventType.COMPLETED, provider_response_id="resp")

    def supports_tools(self):
        return True

    def supports_vision(self):
        return False

    def supports_reasoning_levels(self):
        return True

    def context_limits(self):
        return ContextLimits(1000, 1000)

    async def cancel(self, request_id):
        return None

    async def health(self):
        return ProviderHealth(ProviderHealthState.HEALTHY, "ready")

    @property
    def metadata(self):
        return ProviderMetadata("fake", "fake-model")

    async def close(self):
        return None


def runtime_with_provider():
    provider = FakeProvider()
    settings = RuntimeSettings(default_intelligence_route="primary")
    router = IntelligenceProviderRouter(default_route="primary")
    router.register("primary", provider, make_default=True)
    runtime = JarvisRuntime(settings=settings, provider_router=router, version="0.1.0-test")
    runtime.start()
    runtime.create_conversation(user_id="u", device_id="desktop-test")
    return runtime, provider


class DesktopHostTests(unittest.TestCase):
    def test_health_config_and_versioned_runtime_api_share_one_runtime(self) -> None:
        runtime, provider = runtime_with_provider()
        config = OpenAIRealtimeConfig(api_key="test-key")
        with tempfile.TemporaryDirectory() as directory:
            app = create_desktop_app(runtime=runtime, provider=provider, realtime_config=config, static_dir=Path(directory))
            with TestClient(app) as client:
                health = client.get("/api/desktop/health")
                self.assertEqual(health.status_code, 200)
                payload = health.json()
                self.assertEqual(payload["status"], "ok")
                self.assertEqual(payload["runtime_id"], runtime.runtime_id)
                self.assertEqual(payload["conversation_id"], runtime.conversation.context.conversation_id)
                self.assertEqual(payload["model"], "gpt-realtime-2.1-mini")
                self.assertEqual(payload["voice"], "cedar")
                runtime_health = client.get("/runtime/v1/health")
                self.assertEqual(runtime_health.status_code, 200)
                self.assertEqual(runtime_health.json()["data"]["runtime_id"], runtime.runtime_id)

    def test_missing_built_ui_returns_actionable_page_without_breaking_api(self) -> None:
        runtime, provider = runtime_with_provider()
        config = OpenAIRealtimeConfig(api_key="test-key")
        with tempfile.TemporaryDirectory() as directory:
            app = create_desktop_app(runtime=runtime, provider=provider, realtime_config=config, static_dir=Path(directory))
            with TestClient(app) as client:
                page = client.get("/")
                self.assertEqual(page.status_code, 503)
                self.assertIn("npm run desktop:build", page.text)
                self.assertEqual(client.get("/api/desktop/config").status_code, 200)

    def test_realtime_session_starts_inactive_and_cannot_create_call_without_control_channel(self) -> None:
        runtime, provider = runtime_with_provider()
        session = DesktopRealtimeSession(
            runtime=runtime,
            config=OpenAIRealtimeConfig(api_key="test-key"),
        )
        self.assertFalse(session.active)
        self.assertIsNone(session.call_id)


if __name__ == "__main__":
    unittest.main()
