from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from apps.runtime_api import create_app
from core.runtime import IntelligenceProviderRouter, JarvisRuntime, RuntimeSettings


class RuntimeApiIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = JarvisRuntime(
            settings=RuntimeSettings(
                event_history_limit=64,
                api_event_queue_limit=32,
                api_max_replay_events=32,
                api_heartbeat_seconds=2.0,
            ),
            provider_router=IntelligenceProviderRouter(default_route="primary"),
            version="0.0.7-test",
        )
        self.runtime.start()
        self.client = TestClient(create_app(self.runtime))

    def tearDown(self) -> None:
        self.client.close()
        self.runtime.close()

    def test_http_protocol_health_and_snapshot_are_versioned(self) -> None:
        protocol = self.client.get("/v1/protocol")
        health = self.client.get("/v1/health")
        snapshot = self.client.get("/v1/runtime/snapshot")
        self.assertEqual(protocol.status_code, 200)
        self.assertEqual(health.status_code, 200)
        self.assertEqual(snapshot.status_code, 200)
        for response in (protocol, health, snapshot):
            body = response.json()
            self.assertEqual(body["protocol"], "jarvis-runtime")
            self.assertEqual(body["protocol_version"], 1)
        self.assertEqual(snapshot.json()["data"]["runtime_id"], self.runtime.runtime_id)

    def test_http_event_replay_requires_matching_runtime_identity(self) -> None:
        cursor = self.runtime.snapshot().event_cursor
        self.runtime.event_bus.emit("missed.event", origin="test")
        good = self.client.get(
            "/v1/runtime/events",
            params={"after": cursor, "runtime_id": self.runtime.runtime_id},
        ).json()["data"]
        self.assertTrue(good["resume_accepted"])
        self.assertEqual([item["event_type"] for item in good["events"]], ["missed.event"])

        wrong = self.client.get(
            "/v1/runtime/events",
            params={"after": cursor, "runtime_id": "runtime-old"},
        ).json()["data"]
        self.assertFalse(wrong["resume_accepted"])
        self.assertEqual(wrong["reset_reason"], "runtime-changed")
        self.assertEqual(wrong["events"], [])

    def test_http_replay_limit_is_boundary_validated(self) -> None:
        response = self.client.get(
            "/v1/runtime/events",
            params={"after": 0, "limit": 999},
        )
        self.assertEqual(response.status_code, 400)

    def test_websocket_handshake_snapshot_replay_and_live_event(self) -> None:
        before = self.runtime.snapshot().event_cursor
        self.runtime.event_bus.emit("missed.one", origin="test")
        path = (
            "/v1/runtime/events/ws"
            f"?after={before}&runtime_id={self.runtime.runtime_id}"
            "&client_id=test-client&platform=android&device_id=device-a&protocol_version=1"
        )
        with self.client.websocket_connect(path) as websocket:
            hello = websocket.receive_json()
            sync = websocket.receive_json()
            ready = websocket.receive_json()
            self.assertEqual(hello["type"], "hello")
            self.assertEqual(hello["data"]["platform"], "android")
            self.assertTrue(hello["data"]["platform_is_informational"])
            self.assertEqual(sync["type"], "sync")
            self.assertTrue(sync["data"]["resume_accepted"])
            self.assertEqual(
                [item["event_type"] for item in sync["data"]["replay_events"]],
                ["missed.one"],
            )
            self.assertEqual(ready["type"], "ready")

            event = self.runtime.event_bus.emit("live.one", origin="test")
            message = websocket.receive_json()
            self.assertEqual(message["type"], "event")
            self.assertEqual(message["data"]["event"]["sequence"], event.sequence)

    def test_websocket_runtime_change_forces_reset_not_false_resume(self) -> None:
        self.runtime.event_bus.emit("x", origin="test")
        path = (
            "/v1/runtime/events/ws"
            "?after=1&runtime_id=runtime-old&client_id=test&platform=ios&protocol_version=1"
        )
        with self.client.websocket_connect(path) as websocket:
            websocket.receive_json()  # hello
            sync = websocket.receive_json()
            self.assertFalse(sync["data"]["resume_accepted"])
            self.assertEqual(sync["data"]["reset_reason"], "runtime-changed")
            self.assertEqual(sync["data"]["replay_events"], [])

    def test_websocket_rejects_unknown_protocol_version(self) -> None:
        with self.assertRaises(Exception):
            with self.client.websocket_connect(
                "/v1/runtime/events/ws?client_id=test&platform=ios&protocol_version=999"
            ):
                pass

    def test_client_disconnect_does_not_stop_or_replace_runtime(self) -> None:
        runtime_identity = id(self.runtime)
        cursor = self.runtime.snapshot().event_cursor
        path = (
            "/v1/runtime/events/ws"
            f"?after={cursor}&runtime_id={self.runtime.runtime_id}"
            "&client_id=test&platform=macos&protocol_version=1"
        )
        with self.client.websocket_connect(path) as websocket:
            websocket.receive_json()
            websocket.receive_json()
            websocket.receive_json()
        self.assertEqual(id(self.runtime), runtime_identity)
        self.assertEqual(self.runtime.lifecycle.value, "running")


if __name__ == "__main__":
    unittest.main()
