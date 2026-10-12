"""Repair15: restore silent sleep in overlap; keep other probe tools isolated.

These are source/config contracts, not a claim that Realtime selects the tool
correctly on live audio. Windows voice tests remain required for acceptance.
"""
import unittest
from pathlib import Path

from providers.voice_frontend.openai_realtime.config import OpenAIRealtimeConfig
from providers.voice_frontend.openai_realtime.tool_probe import (
    TOOL_PROBE_TOOLS, OVERLAP_PROBE_TOOLS, OVERLAP_PROBE_INSTRUCTIONS,
    overlap_probe_response_policy, probe_response_policy,
)
from providers.voice_frontend.openai_realtime.webrtc import build_realtime_session

ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / 'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
HOST = (ROOT / 'apps/desktop_alpha.py').read_text(encoding='utf-8')

class OverlapSleepContractTests(unittest.TestCase):
    def test_overlap_has_sleep_tool_with_required_evidence(self):
        self.assertEqual({t['name'] for t in OVERLAP_PROBE_TOOLS}, {'ask_luna', 'test_action', 'sleep_jarvis'})
        self.assertEqual({t['name'] for t in TOOL_PROBE_TOOLS}, {'ask_luna', 'test_action'})
        sleep = next(t for t in OVERLAP_PROBE_TOOLS if t['name'] == 'sleep_jarvis')
        self.assertEqual(sleep['parameters']['required'], ['sleep_evidence'])
        self.assertFalse(sleep['parameters']['additionalProperties'])
        self.assertIn('Gratitude alone', OVERLAP_PROBE_INSTRUCTIONS)

    def test_overlap_policy_and_session_both_expose_sleep(self):
        p = overlap_probe_response_policy()
        self.assertEqual(p['tools'], OVERLAP_PROBE_TOOLS)
        self.assertEqual(p['output_modalities'], ['text'])
        self.assertEqual(p['tool_choice'], 'auto')
        config = OpenAIRealtimeConfig.from_env(env={'OPENAI_API_KEY':'dummy','JARVIS_REALTIME_OVERLAP_PROBE':'1'})
        session = build_realtime_session(config)
        self.assertEqual(session['tools'], OVERLAP_PROBE_TOOLS)
        self.assertEqual(session['output_modalities'], ['text'])
        self.assertEqual(session['instructions'], OVERLAP_PROBE_INSTRUCTIONS)

    def test_text_only_probe_unchanged(self):
        self.assertEqual(probe_response_policy()['tools'], TOOL_PROBE_TOOLS)
        config = OpenAIRealtimeConfig.from_env(env={'OPENAI_API_KEY':'dummy','JARVIS_REALTIME_TOOL_SELECTION_PROBE':'1'})
        session = build_realtime_session(config)
        self.assertEqual(session['tools'], TOOL_PROBE_TOOLS)

    def test_server_enables_lifecycle_tool_only_for_overlap(self):
        self.assertIn('overlap_probe_response_policy() if overlap_probe else probe_response_policy() if tool_probe', HOST)
        self.assertIn('if not self.config.overlap_probe:', HOST)

    def test_decision_model_knows_sleep_without_hardcoded_keyword_routing(self):
        self.assertIn('Set sleep_evidence to the exact contiguous closing words', APP)
        self.assertIn('Mere gratitude does not authorize sleep', APP)
        self.assertIn("tools,tool_choice:'auto'", APP)
        self.assertIn("metadata:{jarvis_stage:'overlap_decision'", APP)

    def test_sleep_requires_evidence_and_uses_existing_lifecycle(self):
        self.assertIn("if (tool === 'sleep_jarvis')", APP)
        self.assertIn('JSON.parse(calls[0].arguments', APP)
        self.assertIn("sleep_evidence || ''", APP)
        self.assertIn('calls.length === 1 && evidence.length > 0 && evidence.length <= 160', APP)
        self.assertIn("void enterSleep('voice_command');", APP)
        self.assertIn("phase:'sleep'", APP)
        self.assertIn("phase:'sleep_rejected'", APP)
        self.assertIn("reason:'missing_or_invalid_sleep_evidence'", APP)

    def test_sleep_does_not_publish_audio_and_wake_still_restarts(self):
        self.assertIn("overlapGateRef.current?.abort();", APP)
        self.assertIn('await stopRealtimeSession({ notifyServer: false });', APP)
        self.assertIn("if (!stoppingRef.current) await startWakeListening();", APP)
        self.assertIn('if (overlapProbeRef.current) cancelOverlap();', APP)
        self.assertIn("output_modalities:['audio'],max_output_tokens:1024,tools:[],tool_choice:'none'", APP)

if __name__ == '__main__':
    unittest.main()
