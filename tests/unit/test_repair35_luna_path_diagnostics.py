import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class Repair35LunaPathDiagnosticsTests(unittest.TestCase):
    def test_provider_records_continuation_and_actual_service_tier(self):
        text = (
            ROOT / "providers/intelligence/openai/provider.py"
        ).read_text(encoding="utf-8")
        self.assertIn("latest_request_diagnostics", text)
        self.assertIn("continuation=continuation", text)
        self.assertIn("actual_service_tier=getattr(response", text)
        self.assertIn('metadata["service_tier"]', text)

    def test_voice_lab_exposes_fast_ab_and_prints_path(self):
        text = (ROOT / "apps/voice_lab.py").read_text(encoding="utf-8")
        self.assertIn('"--luna-service-tier"', text)
        self.assertIn("Luna path:", text)
        self.assertIn("continuation=", text)
        self.assertIn("actual_tier=", text)

    def test_latency_probe_matches_voice_websocket_transport(self):
        text = (ROOT / "apps/luna_latency_probe.py").read_text(encoding="utf-8")
        self.assertIn('"--transport"', text)
        self.assertIn('default="websocket"', text)
        self.assertIn("core continuation=", text)

    def test_humanization_and_whole_response_are_untouched(self):
        conversation = (ROOT / "core/conversation/engine.py").read_text(encoding="utf-8")
        voice = (ROOT / "core/voice/engine.py").read_text(encoding="utf-8")
        self.assertIn("Then elaborate naturally if useful", conversation)
        self.assertIn('if self.tts_response_mode == "whole":', voice)


if __name__ == "__main__":
    unittest.main()
