import unittest

from core.diagnostics import collect_diagnostics


class DiagnosticsTests(unittest.TestCase):
    def test_reports_conversation_core_without_live_network_probe(self) -> None:
        data = collect_diagnostics()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["network_probe"], "not-run")
        self.assertEqual(data["external_actions"], "disabled-in-core-diagnostics")
        self.assertEqual(data["providers"]["intelligence"], "provider-layer-ready")
        self.assertEqual(data["conversation"]["context"], "ready")
        self.assertEqual(data["conversation"]["referent_resolver"], "ready")
        self.assertEqual(data["conversation"]["event_bus"], "ready")
        self.assertEqual(data["conversation"]["state_machine"], "ready")
        self.assertEqual(data["conversation"]["typed_path"], "ready")


if __name__ == "__main__":
    unittest.main()
