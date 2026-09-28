import unittest
from pathlib import Path

from providers.intelligence.openai.config import DEFAULT_MODEL, DEFAULT_SERVICE_TIER, OpenAIProviderConfig

ROOT = Path(__file__).resolve().parents[2]


class Repair36LunaModelControlTests(unittest.TestCase):
    def test_default_is_gpt6_luna_on_standard_processing(self):
        config = OpenAIProviderConfig.from_env({})
        self.assertEqual(DEFAULT_MODEL, "gpt-6-luna")
        self.assertEqual(config.model, "gpt-6-luna")
        self.assertEqual(DEFAULT_SERVICE_TIER, "default")
        self.assertEqual(config.service_tier, "default")

    def test_env_can_pin_any_exact_model_id(self):
        config = OpenAIProviderConfig.from_env({
            "JARVIS_OPENAI_MODEL": "gpt-5.6-luna",
            "JARVIS_OPENAI_SERVICE_TIER": "default",
        })
        self.assertEqual(config.model, "gpt-5.6-luna")
        self.assertEqual(config.service_tier, "default")

    def test_voice_lab_exposes_manual_model_override(self):
        text = (ROOT / "apps/voice_lab.py").read_text(encoding="utf-8")
        self.assertIn('"--luna-model"', text)
        self.assertIn('config_updates["model"] = args.luna_model', text)
        self.assertIn("Luna selection:", text)

    def test_probe_exposes_exact_model_ab(self):
        text = (ROOT / "apps/luna_latency_probe.py").read_text(encoding="utf-8")
        self.assertIn('"--model"', text)
        self.assertIn('updates["model"] = args.model', text)

    def test_continuation_state_is_committed_before_terminal_yield(self):
        text = (ROOT / "providers/intelligence/openai/provider.py").read_text(encoding="utf-8")
        commit_index = text.index("lane_committed=True")
        yield_index = text.index("for item in converted:", commit_index)
        self.assertLess(commit_index, yield_index)


if __name__ == "__main__":
    unittest.main()
