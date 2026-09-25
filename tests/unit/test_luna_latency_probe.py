import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "apps" / "luna_latency_probe.py"


class LunaLatencyProbeTests(unittest.TestCase):
    def test_probe_compares_raw_provider_and_conversation_core_ttft(self):
        text = PROBE.read_text(encoding="utf-8")
        self.assertIn("raw Luna TTFT average", text)
        self.assertIn("Conversation Core TTFT average", text)
        self.assertIn("apparent Core/app overhead", text)
        self.assertIn('choices=["auto", "default", "fast", "priority"]', text)
        self.assertIn('ReasoningPolicy(level="none"', text)


if __name__ == "__main__":
    unittest.main()
