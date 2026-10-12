"""Repair10: compound dismissal policy and verified authorization are kept separate."""
from __future__ import annotations
import unittest
from pathlib import Path
from providers.voice_frontend.openai_realtime.tool_probe import (
    OVERLAP_SLEEP_TOOL, OVERLAP_PROBE_INSTRUCTIONS, TOOL_PROBE_TOOLS,
)
ROOT=Path(__file__).resolve().parents[2]
APP=(ROOT/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')

class CompoundSleepContracts(unittest.TestCase):
    def test_model_understands_polite_signoff_vs_plain_gratitude(self):
        selection=APP.split('const requestOverlapResponses =',1)[1].split('const awaitOverlapAudioCommit =',1)[0]
        self.assertEqual(selection.count('Classify the entire current user utterance'),2)
        self.assertEqual(selection.count('A clear closing or dismissal takes precedence'),2)
        self.assertEqual(selection.count('Thanks Jarvis, that'),4)
        self.assertEqual(selection.count('Mere gratitude does not authorize sleep'),2)
        self.assertIn('a quoted closing phrase',OVERLAP_SLEEP_TOOL['description'])
        self.assertIn('gratitude comes BEFORE the dismissal', OVERLAP_PROBE_INSTRUCTIONS)
    def test_model_only_selects_sleep_and_ui_verifies_actual_words(self):
        self.assertIn('tools,tool_choice:\'auto\'',APP)
        self.assertIn('isVerifiedSleepEvidence(',APP)
        self.assertIn("reason:'verified_user_sleep_request'",APP)
        self.assertIn("phase:'sleep_rejected'",APP)
        self.assertIn("phase:'direct_pending_transcription'",APP)
        self.assertEqual({x['name'] for x in TOOL_PROBE_TOOLS},{'ask_luna','test_action'})
    def test_pcm_core_luna_and_decisions_wiring_unchanged(self):
        self.assertIn("metadata:{jarvis_stage:'core_luna_voice'",APP)
        self.assertIn("output_modalities:['audio'],max_output_tokens:1024",APP)
        self.assertIn('overlapDirectVerifiedRef.current',APP)
        self.assertIn('decisions_shadow', (ROOT/'apps/desktop_alpha.py').read_text(encoding='utf-8'))

if __name__=='__main__': unittest.main()
