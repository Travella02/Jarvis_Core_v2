from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from core.common.ids import CorrelationContext
from core.conversation import EventBus
from core.runtime import IntelligenceProviderRouter, JarvisRuntime, RuntimeSettings
from core.runtime.protocol import (
    PROTOCOL_NAME,
    PROTOCOL_VERSION,
    RuntimeProtocolError,
    envelope,
    event_to_dict,
    protocol_description,
    snapshot_to_dict,
)


class RuntimeProtocolTests(unittest.TestCase):
    def _runtime(self) -> JarvisRuntime:
        runtime = JarvisRuntime(
            settings=RuntimeSettings(),
            provider_router=IntelligenceProviderRouter(default_route="primary"),
            version="0.0.7-test",
        )
        runtime.start()
        return runtime

    def test_protocol_is_versioned_and_platform_neutral(self) -> None:
        description = protocol_description()
        self.assertEqual(description["name"], PROTOCOL_NAME)
        self.assertEqual(description["version"], PROTOCOL_VERSION)
        self.assertEqual(description["transports"], ["http-json", "websocket-json"])
        for platform in ("windows", "macos", "linux", "ios", "android"):
            self.assertIn(platform, description["client_platforms"])
        self.assertNotIn("electron", json.dumps(description).lower())

    def test_event_serialization_preserves_trace_and_utc_timestamp(self) -> None:
        bus = EventBus()
        trace = CorrelationContext.create()
        event = bus.emit("demo.event", origin="test", trace=trace, payload={"ok": True})
        wire = event_to_dict(event)
        self.assertEqual(wire["trace"]["correlation_id"], trace.correlation_id)
        self.assertTrue(wire["timestamp"].endswith("Z"))
        self.assertEqual(wire["payload"], {"ok": True})

    def test_protocol_rejects_opaque_binary_payloads(self) -> None:
        bus = EventBus()
        event = bus.emit("bad.event", origin="test", payload={"audio": b"secret-binary"})
        with self.assertRaises(RuntimeProtocolError):
            event_to_dict(event)

    def test_snapshot_serialization_contains_no_secret_provider_fields(self) -> None:
        runtime = self._runtime()
        try:
            wire = snapshot_to_dict(runtime.snapshot())
            text = json.dumps(wire)
            self.assertEqual(wire["runtime_id"], runtime.runtime_id)
            self.assertEqual(wire["version"], "0.0.7-test")
            self.assertNotIn("api_key", text.lower())
            self.assertNotIn("token", text.lower())
            self.assertEqual(wire["settings"]["api_exposure"], "loopback-only")
        finally:
            runtime.close()

    def test_envelope_has_stable_top_level_contract(self) -> None:
        payload = envelope("demo", data={"when": datetime(2026, 10, 5, tzinfo=timezone.utc)})
        self.assertEqual(set(payload), {"protocol", "protocol_version", "type", "data"})
        self.assertEqual(payload["protocol"], PROTOCOL_NAME)
        self.assertEqual(payload["protocol_version"], PROTOCOL_VERSION)
        self.assertEqual(payload["data"]["when"], "2026-10-05T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
