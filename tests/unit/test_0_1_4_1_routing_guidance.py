"""0.1.4.1: opt-in routing guidance and offline comparison, no audio authority change."""
from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest.mock import patch
from scripts import realtime_ab
from scripts.repair_0_1_4_1_routing_report import CASES, parse_log, report, format_report
from providers.voice_frontend.openai_realtime.config import OpenAIRealtimeConfig

ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / 'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
HOST = (ROOT / 'apps/desktop_alpha.py').read_text(encoding='utf-8')

class GuidanceTests(unittest.TestCase):
    def test_modes_exactly_one_env_difference(self):
        modes=[]
        def capture(_args, *, cwd, env, shell):
            modes.append({k:v for k,v in env.items() if k.startswith('JARVIS_')})
            return 0
        for arm in ('mini-overlap-luna-trim','mini-overlap-luna-trim-guided'):
            with patch('sys.argv',['realtime_ab.py',arm]),patch.object(realtime_ab.subprocess,'call',side_effect=capture):
                self.assertEqual(realtime_ab.main(),0)
        before,after=modes
        self.assertEqual(before['JARVIS_0141_DELEGATION_GUIDANCE'],'0')
        self.assertEqual(after['JARVIS_0141_DELEGATION_GUIDANCE'],'1')
        self.assertEqual({k:v for k,v in before.items() if k != 'JARVIS_0141_DELEGATION_GUIDANCE'},
                         {k:v for k,v in after.items() if k != 'JARVIS_0141_DELEGATION_GUIDANCE'})
        for mode in modes:
            self.assertEqual(mode['JARVIS_CORE_LUNA_PROBE'],'1')
            self.assertEqual(mode['JARVIS_PCM_TRIM_LEADING_SILENCE'],'1')
            self.assertEqual(mode['JARVIS_LUNA_RESULT_HOLD_SECONDS'],'0')
            self.assertEqual(mode['JARVIS_DECISIONS_SHADOW_PROBE'],'0')

    def test_flag_defaults_off_and_validated(self):
        self.assertFalse(OpenAIRealtimeConfig.from_env({}).delegation_guidance_probe)
        self.assertTrue(OpenAIRealtimeConfig.from_env({'JARVIS_0141_DELEGATION_GUIDANCE':'1'}).delegation_guidance_probe)
        with self.assertRaises(ValueError):
            OpenAIRealtimeConfig.from_env({'JARVIS_0141_DELEGATION_GUIDANCE':'maybe'})
        self.assertIn('guidance requires real Core/Luna overlap mode', HOST)

    def test_authority_unchanged_and_guidance_only_in_decision(self):
        self.assertIn('delegationGuidanceRef.current && coreLunaProbeRef.current && !wakeOnly',APP)
        self.assertIn('the same Mini router, NOT an additional model call',APP)
        self.assertIn('Preserve sleep_evidence validation and external-action dry-run rules exactly',APP)
        self.assertIn('"delegation_guidance_probe": self.config.delegation_guidance_probe',HOST)
        self.assertIn("overlapGateRef.current?.abort()",APP)
        self.assertIn("const realLuna = coreLunaProbeRef.current && completed && calls.length === 1 && tool === 'ask_luna'",APP)
        self.assertIn("if (overlapDecisionRef.current === 'direct')",APP)
        self.assertIn("phase:'sleep_evidence_check'",APP)

    def test_offline_report_no_raw_speech_and_missing_is_not_accuracy(self):
        sample='''[Jarvis Tool Probe] turn=2 | tool=none | phase=selection | decision_ms=500
[Jarvis Latency Detail] turn=2 | commit_ms=1 | route_ms=500 | first_audio_ms=675
[Jarvis Tool Probe] turn=4 | tool=ask_luna | phase=selection
[Jarvis Luna] turn=4 | phase=result | status=completed | elapsed_ms=3200
[USER SPEECH] turn=5 | text="private personal transcript secret"
'''
        rows=parse_log(sample)
        self.assertEqual(rows[2]['first_audio_ms'],675)
        self.assertEqual(rows[4]['core_result'],'completed')
        self.assertNotIn('private',str(rows))
        data=report(rows)
        self.assertEqual(data['known'],2)
        self.assertFalse(data['complete'])
        self.assertEqual(data['correct'],2)
        text=format_report('Test',data)
        self.assertNotIn('personal transcript',text)
        self.assertIn('incomplete or extra turns',text)
        self.assertEqual(len(CASES),12)

    def test_duplicate_tool_routes_are_ambiguous(self):
        row=parse_log('[Jarvis Tool Probe] turn=2 | tool=none | phase=selection\n[Jarvis Tool Probe] turn=2 | tool=ask_luna | phase=selection')
        self.assertEqual(report(row)['cases'][0][3],'ambiguous')

if __name__=='__main__': unittest.main()
