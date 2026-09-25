import ast
import unittest
from pathlib import Path

from core.intelligence import ReasoningPolicy
from providers.intelligence.openai.config import OpenAIProviderConfig
from providers.intelligence.openai.serialization import reasoning_effort


ROOT = Path(__file__).resolve().parents[2]


class FastReasoningPolicyTests(unittest.TestCase):
    def test_default_policy_is_lowest_reasoning_without_automatic_escalation(self):
        policy = ReasoningPolicy()
        self.assertEqual(policy.level, "none")
        self.assertFalse(policy.allow_escalation)
        config = OpenAIProviderConfig(api_key="test")
        self.assertEqual(reasoning_effort(policy, config), "none")

    def test_all_development_labs_default_to_none(self):
        for rel in ("apps/intelligence_lab.py", "apps/conversation_lab.py", "apps/voice_lab.py"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn('default="none"', text, rel)

    def test_conversation_core_default_does_not_reintroduce_standard_reasoning(self):
        text = (ROOT / "core/conversation/engine.py").read_text(encoding="utf-8")
        tree = ast.parse(text)
        self.assertNotIn('ReasoningPolicy(level="standard")', text)
        self.assertIn("ReasoningPolicy()", text)


if __name__ == "__main__":
    unittest.main()
