"""Regression tests for browser-bridge A/B startup flags; never launches npm or audio."""
from __future__ import annotations
import os
import sys
import unittest
from unittest.mock import patch
from scripts import realtime_ab


class BrowserBridgeStartupRepairTests(unittest.TestCase):
    def launch_env(self, mode):
        called = []

        def fake_call(cmd, cwd=None, env=None, shell=None):
            called.append((cmd, cwd, dict(env or {})))
            return 0

        with patch.object(sys, 'argv', ['scripts/realtime_ab.py', mode]):
            with patch('subprocess.call', side_effect=fake_call):
                result = realtime_ab.main()
        self.assertEqual(result, 0)
        self.assertEqual(len(called), 1)
        self.assertEqual(called[0][0], ['npm', 'run', 'desktop'])
        return called[0][2]

    def test_browser_bridge_enables_all_core_flags(self):
        env = self.launch_env('mini-overlap-luna-trim-guided-browser-bridge')
        for key in (
            'JARVIS_REALTIME_OVERLAP_PROBE',
            'JARVIS_CORE_LUNA_PROBE',
            'JARVIS_PCM_TRIM_LEADING_SILENCE',
            'JARVIS_0141_DELEGATION_GUIDANCE',
            'JARVIS_CORE_ACTIONS_PROBE',
            'JARVIS_SEMANTIC_ACTIONS_PROBE',
            'JARVIS_BROWSER_BRIDGE_PROBE',
            'JARVIS_BROWSER_MEDIA_PROBE',
            'JARVIS_PHONETIC_WAKE',
        ):
            with self.subTest(key=key):
                self.assertEqual(env[key], '1')
        self.assertEqual(env['JARVIS_MANAGED_BROWSER_PROBE'], '0')
        self.assertEqual(env['JARVIS_PARALLEL_SHADOW_PROBE'], '0')

    def test_every_core_luna_mode_also_enables_overlap(self):
        for name in realtime_ab.MODELS:
            env = self.launch_env(name)
            with self.subTest(name=name):
                if env['JARVIS_CORE_LUNA_PROBE'] == '1':
                    self.assertEqual(env['JARVIS_REALTIME_OVERLAP_PROBE'], '1')
                if name.startswith('mini-overlap-luna-trim'):
                    self.assertEqual(env['JARVIS_PCM_TRIM_LEADING_SILENCE'], '1')

    def test_existing_managed_mode_still_works(self):
        env = self.launch_env('mini-overlap-luna-trim-guided-browser-media')
        self.assertEqual(env['JARVIS_MANAGED_BROWSER_PROBE'], '1')
        self.assertEqual(env['JARVIS_BROWSER_BRIDGE_PROBE'], '0')
        self.assertEqual(env['JARVIS_REALTIME_OVERLAP_PROBE'], '1')


if __name__ == '__main__':
    unittest.main()
