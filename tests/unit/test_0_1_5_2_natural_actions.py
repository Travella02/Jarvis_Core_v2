"""0.1.5.2 Core action acceptance: real effect requires explicit, same-turn user text."""
from __future__ import annotations
import asyncio
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from apps.desktop_actions import DesktopActionSession
from apps import desktop_cancel_cue

ROOT = Path(__file__).resolve().parents[2]

class ActionSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.urls = []
        self.s = DesktopActionSession(launcher=lambda url: self.urls.append(url) or True)
        self.s.on_turn_started(1)

    async def call(self, turn=1, tool='test_action', text='Jarvis, open YouTube',
                   source='voice', binding='item_abc123'):
        return await self.s.handle(turn=turn,selected_tool=tool,source=source,
                                   binding=binding,transcript=text)

    async def test_voice_open_real_action(self):
        r = await self.call()
        self.assertEqual(r.status, 'completed')
        self.assertIn('default browser',r.text)
        self.assertEqual(self.urls, ['https://www.youtube.com/'])

    async def test_typed_open_real_action(self):
        r = await self.call(text='open youtube please', source='typed', binding='typed:1')
        self.assertEqual(r.status,'completed')
        self.assertEqual(len(self.urls),1)

    async def test_model_call_without_evidence_never_opens(self):
        for v in [('', 'voice','item_abc123'),('open YouTube','voice',''),('open YouTube','unknown','item_abc123')]:
            self.s.on_turn_started(self.s.active_turn+1)
            r=await self.call(turn=self.s.active_turn,text=v[0],source=v[1],binding=v[2])
            self.assertEqual(r.status,'failed')
        self.assertEqual(self.urls,[])

    async def test_unrecognized_tools_and_compound_requests_fail(self):
        r=await self.call(tool='ask_luna')
        self.assertEqual(r.status,'failed')
        self.s.on_turn_started(2)
        r=await self.call(turn=2,text='open YouTube and run my code')
        self.assertEqual(r.status,'failed')
        self.assertFalse(self.urls)

    async def test_quote_negation_and_other_sites_never_open(self):
        for text in ('Please do not open YouTube','What does open YouTube mean?',
                     'Open Google','Jarvis, open https://evil.example',
                     'Someone said: open YouTube'):
            self.s.on_turn_started(self.s.active_turn+1)
            r=await self.call(turn=self.s.active_turn,text=text)
            self.assertEqual(r.status,'failed',text)
        self.assertEqual(self.urls,[])

    async def test_old_turn_does_not_open_after_new_turn(self):
        self.s.on_turn_started(2)
        self.assertIsNone(await self.call())
        self.assertEqual(self.urls,[])

    async def test_duplicate_same_turn_executes_once(self):
        r1,r2=await asyncio.gather(self.call(),self.call())
        self.assertEqual(sum(r is not None for r in (r1,r2)),1)
        self.assertEqual(len(self.urls),1)

    async def test_unavailable_browser_no_false_success(self):
        self.s=DesktopActionSession(launcher=lambda _: False)
        self.s.on_turn_started(1)
        r=await self.call()
        self.assertEqual(r.status,'failed')
        self.assertEqual(r.code,'browser_launch_failed')
        self.assertEqual(self.urls,[])

class IntegrationContracts(unittest.TestCase):
    def test_flag_only_in_separate_action_arm(self):
        script=(ROOT/'scripts/realtime_ab.py').read_text(encoding='utf-8')
        self.assertIn('"mini-overlap-luna-trim-guided-actions"',script)
        self.assertIn('JARVIS_CORE_ACTIONS_PROBE',script)
        self.assertIn('JARVIS_SILENT_TEST_CUES',script)

    def test_ui_action_waits_for_independent_matching_item(self):
        app=(ROOT/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
        self.assertIn("input.binding !== overlapInputBindingRef.current",app)
        self.assertIn("settlePendingOverlapAction();",app)
        self.assertIn("kind:'desktop_action_request'",app)
        self.assertIn("payload.kind === 'core_tool_result'",app)
        self.assertIn('overlapPendingActionRef.current = null;',app)
        self.assertIn("if (payload.cue_route !== 'native_windows' && payload.cue_route !== 'silent')",app)

    def test_core_never_executes_user_supplied_url(self):
        host=(ROOT/'apps/desktop_alpha.py').read_text(encoding='utf-8')
        self.assertIn('DesktopActionSession',host)
        self.assertIn('await self._action_session.handle(',host)
        self.assertNotIn('webbrowser.open',host)

    def test_silent_test_cue_never_calls_winsound(self):
        fake=types.SimpleNamespace(SND_MEMORY=4,SND_NODEFAULT=2,
                                   PlaySound=lambda *_: self.fail('beep should not play'))
        with patch.dict(os.environ,{'JARVIS_SILENT_TEST_CUES':'1'}), \
             patch.object(desktop_cancel_cue.sys,'platform','win32'), \
             patch.dict(sys.modules,{'winsound':fake}):
            self.assertEqual(desktop_cancel_cue.play_native_hold_cue(), 'silenced_by_test_setting')

if __name__ == '__main__': unittest.main()
