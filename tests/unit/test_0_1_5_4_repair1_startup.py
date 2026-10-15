"""0.1.5.4 Repair1: launch flags must satisfy the real Core/Luna guidance gate."""
from __future__ import annotations
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('jarvis_realtime_ab_0154_r1', ROOT/'scripts/realtime_ab.py')
SCRIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCRIPT)

class ManagedBrowserLaunchTests(unittest.TestCase):
    def capture(self,mode):
        with patch.object(sys,'argv',['realtime_ab.py',mode]), patch.object(subprocess,'call',return_value=0) as called:
            self.assertEqual(SCRIPT.main(),0)
        return called.call_args.kwargs['env']

    def test_managed_browser_flags_authorize_real_core_luna(self):
        env=self.capture('mini-overlap-luna-trim-guided-managed-browser')
        for key in (
            'JARVIS_REALTIME_OVERLAP_PROBE',
            'JARVIS_CORE_LUNA_PROBE',
            'JARVIS_PCM_TRIM_LEADING_SILENCE',
            'JARVIS_0141_DELEGATION_GUIDANCE',
            'JARVIS_CORE_ACTIONS_PROBE',
            'JARVIS_SEMANTIC_ACTIONS_PROBE',
            'JARVIS_MANAGED_BROWSER_PROBE',
        ):
            self.assertEqual(env[key],'1',key)
        self.assertEqual(env['JARVIS_REALTIME_MODEL'],'gpt-realtime-2.1-mini')
        self.assertEqual(env['JARVIS_PARALLEL_SHADOW_PROBE'],'0')

    def test_accepted_semantic_mode_unchanged(self):
        env=self.capture('mini-overlap-luna-trim-guided-semantic')
        self.assertEqual(env['JARVIS_CORE_LUNA_PROBE'],'1')
        self.assertEqual(env['JARVIS_0141_DELEGATION_GUIDANCE'],'1')
        self.assertEqual(env['JARVIS_MANAGED_BROWSER_PROBE'],'0')
        self.assertEqual(env['JARVIS_CORE_ACTIONS_PROBE'],'1')

    def test_other_modes_do_not_enable_managed_browser(self):
        for mode in ('mini','mini-overlap-luna-trim-guided','mini-overlap-luna-trim-guided-actions'):
            with self.subTest(mode=mode):
                env=self.capture(mode)
                self.assertEqual(env['JARVIS_MANAGED_BROWSER_PROBE'],'0')

if __name__=='__main__': unittest.main()
