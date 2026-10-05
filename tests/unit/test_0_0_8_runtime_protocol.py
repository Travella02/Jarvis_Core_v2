from __future__ import annotations

import unittest

from core.runtime.protocol import protocol_description


class RuntimeClientInputProtocolTests(unittest.TestCase):
    def test_protocol_advertises_typed_input_and_cancel_without_platform_fork(self) -> None:
        description = protocol_description()
        client_input = description["client_input"]
        self.assertEqual(client_input["typed_command"], "POST /v1/runtime/commands/typed")
        self.assertEqual(
            client_input["cancel_command"],
            "POST /v1/runtime/commands/{command_id}/cancel",
        )
        self.assertEqual(client_input["result_delivery"], "authoritative-event-stream")
        self.assertEqual(client_input["idempotency"], "runtime-scoped-client-request-id")
        self.assertEqual(description["version"], 1)
        self.assertEqual(
            description["client_platforms"],
            ["windows", "macos", "linux", "ios", "android"],
        )

    def test_remote_transport_remains_deferred(self) -> None:
        description = protocol_description()
        self.assertEqual(description["remote_transport"], "deferred-authenticated-transport")


if __name__ == "__main__":
    unittest.main()
