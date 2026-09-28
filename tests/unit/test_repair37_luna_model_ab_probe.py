import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class Repair37LunaModelABProbeTests(unittest.TestCase):
    def test_probe_uses_only_conversation_core_measurements(self):
        text = (ROOT / "apps/luna_model_ab_probe.py").read_text(encoding="utf-8")
        self.assertIn("Conversation Core TTFT", text)
        self.assertNotIn("_raw_once", text)
        self.assertNotIn("raw provider TTFT", text)

    def test_probe_alternates_model_order(self):
        text = (ROOT / "apps/luna_model_ab_probe.py").read_text(encoding="utf-8")
        self.assertIn("if index % 2 == 1", text)
        self.assertIn("(args.model_a, args.model_b)", text)
        self.assertIn("(args.model_b, args.model_a)", text)

    def test_probe_warms_both_models_before_measurement(self):
        text = (ROOT / "apps/luna_model_ab_probe.py").read_text(encoding="utf-8")
        self.assertIn("await _warm(core_a, provider_a, args.model_a)", text)
        self.assertIn("await _warm(core_b, provider_b, args.model_b)", text)

    def test_probe_reports_distribution_and_continuation_health(self):
        text = (ROOT / "apps/luna_model_ab_probe.py").read_text(encoding="utf-8")
        self.assertIn("median=", text)
        self.assertIn("p90=", text)
        self.assertIn("Healthy continuation samples:", text)
        self.assertIn('sample.continuation_reason == "exact_chain"', text)
        self.assertIn("sample.input_items == 1", text)

    def test_standard_pricing_is_default(self):
        text = (ROOT / "apps/luna_model_ab_probe.py").read_text(encoding="utf-8")
        self.assertIn('default="default"', text)


if __name__ == "__main__":
    unittest.main()
