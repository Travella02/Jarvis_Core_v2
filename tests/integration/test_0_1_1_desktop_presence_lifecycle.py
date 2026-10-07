from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from apps.desktop_alpha import create_desktop_app
from tests.integration.test_0_1_0_desktop_host import runtime_with_provider
from providers.voice_frontend.openai_realtime import OpenAIRealtimeConfig


class DesktopPresenceLifecycleTests(unittest.TestCase):
    def test_desktop_starts_sleeping_and_exposes_local_wake_configuration(self) -> None:
        runtime, provider = runtime_with_provider()
        with tempfile.TemporaryDirectory() as directory:
            app = create_desktop_app(
                runtime=runtime,
                provider=provider,
                realtime_config=OpenAIRealtimeConfig(api_key="test-key"),
                static_dir=Path(directory),
            )
            with TestClient(app) as client:
                config = client.get("/api/desktop/config").json()
                health = client.get("/api/desktop/health").json()
                self.assertEqual(config["initial_presence"], "sleeping")
                self.assertEqual(config["idle_sleep_seconds"], 60.0)
                self.assertIn("jarvis", config["wake_phrases"])
                self.assertFalse(config["local_wake"])
                self.assertEqual(health["presence"], "sleeping")
                self.assertFalse(health["realtime_active"])

    def test_manual_wake_and_sleep_change_core_presence_without_creating_second_runtime(self) -> None:
        runtime, provider = runtime_with_provider()
        runtime_id = runtime.runtime_id
        with tempfile.TemporaryDirectory() as directory:
            app = create_desktop_app(
                runtime=runtime,
                provider=provider,
                realtime_config=OpenAIRealtimeConfig(api_key="test-key"),
                static_dir=Path(directory),
            )
            with TestClient(app) as client:
                wake = client.post("/api/presence/wake", json={"reason": "typed_wake"})
                self.assertEqual(wake.status_code, 200)
                self.assertEqual(client.get("/api/desktop/health").json()["presence"], "awake")
                sleep = client.post("/api/presence/sleep", json={"reason": "user_done"})
                self.assertEqual(sleep.status_code, 200)
                health = client.get("/api/desktop/health").json()
                self.assertEqual(health["presence"], "sleeping")
                self.assertEqual(health["runtime_id"], runtime_id)

    def test_wake_websocket_fails_closed_when_local_listener_is_unavailable(self) -> None:
        runtime, provider = runtime_with_provider()
        with tempfile.TemporaryDirectory() as directory:
            app = create_desktop_app(
                runtime=runtime,
                provider=provider,
                realtime_config=OpenAIRealtimeConfig(api_key="test-key"),
                static_dir=Path(directory),
            )
            with TestClient(app) as client:
                with client.websocket_connect("/ws/wake") as websocket:
                    payload = websocket.receive_json()
                    self.assertEqual(payload["kind"], "wake_unavailable")
                    self.assertIn("not configured", payload["detail"])


if __name__ == "__main__":
    unittest.main()
