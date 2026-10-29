"""Regression checks for cache-stable, general-purpose task continuation guidance.

These are static contract checks, not assertions about a remote model's behavior.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'apps/desktop/ui/src/App.tsx'


class ContinuationPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = APP.read_text(encoding='utf-8')
        cls.decision_start = cls.text.index('metadata:{jarvis_stage:\'overlap_decision\'')
        cls.decision_end = cls.text.index('metadata:{jarvis_stage:\'overlap_candidate\'', cls.decision_start)
        cls.decision = cls.text[cls.decision_start:cls.decision_end]

    def test_stable_instructions_first_and_changing_context_last(self):
        section = self.decision
        self.assertIn('instructions:(coreLunaProbeRef.current', section)
        self.assertIn('+ recentContextNote}}));', section)
        self.assertNotIn('instructions:recentContextNote +', section)
        self.assertGreater(section.index('+ recentContextNote}}));'),
                           section.index('This applies to any supported task'))

    def test_context_is_verified_and_bounded(self):
        self.assertIn('verifiedActionContextRef.current', self.text)
        self.assertIn('lastVerified.turn === latencyRef.current.turn - 1', self.text)
        self.assertIn('performance.now() - lastVerified.at <= 15000', self.text)
        self.assertIn("context?.category === 'browser'", self.text)
        self.assertIn("if (completed && context?.category === 'browser'", self.text)

    def test_policy_is_generic_not_fixed_scroll_command(self):
        self.assertIn('This applies to any supported task, not just scrolling', self.decision)
        self.assertIn('appropriate tool, target, and direction', self.decision)
        self.assertIn('do not automatically turn it into small talk', self.decision)
        self.assertNotIn("if (text === 'keep going')", self.decision)

    def test_no_implicit_permission(self):
        self.assertIn('verified context is not authorization', self.decision)
        self.assertIn('Every tool action must pass fresh Core checks', self.decision)
        self.assertIn('negation, hypothetical phrasing', self.decision)

    def test_speculative_audio_path_not_modified(self):
        self.assertIn("metadata:{jarvis_stage:'overlap_candidate'", self.text)
        self.assertIn("output_modalities:['audio'],max_output_tokens:1024,tools:[],tool_choice:'none'", self.text)

if __name__ == '__main__':
    unittest.main()
