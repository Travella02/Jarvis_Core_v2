"""0.1.5.7 independent app authority and non-regression contracts. No OS launch."""
from __future__ import annotations

import asyncio
from pathlib import Path
import unittest

from apps.desktop_unified_actions import UnifiedDesktopActionSession
from core.common.ids import CorrelationContext
from core.tools import ToolRequest, ToolResultStatus
from core.tools.desktop_apps import CoreDesktopAppGateway, APP_CATALOG
from core.tools.gateway import ConfirmedUserAction

ROOT = Path(__file__).resolve().parents[2]


class StubBrowser:
    def __init__(self): self.calls=[]; self.last_navigation_verified=True; self.last_system_handoff=False
    async def navigate(self,url): self.calls.append(('navigate',url)); return True
    async def close(self): return None


class CoreAppTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.launched=[]
        self.gateway=CoreDesktopAppGateway(launcher=lambda app: self.launched.append(app) or True)
        self.trace=CorrelationContext.create()

    async def ask(self,text,app='notepad',trace=None,*,evidence=True, arguments=None):
        trace=trace or self.trace
        req=ToolRequest(trace,'desktop_app','launch',arguments if arguments is not None else {'app':app},idempotency_key='this-turn')
        return await self.gateway.execute(req,evidence=ConfirmedUserAction(trace.turn_id,text,True,True) if evidence else None)

    async def test_natural_phrasing_preserves_model_selected_app(self):
        for app,text in [
            ('notepad','Jarvis, could you please open Notepad for me?'),
            ('calculator','Thanks Jarvis, that was useful. Can you bring up Calculator?'),
            ('file_explorer','Hey Jarvis, pull up File Explorer please.'),
        ]:
            result=await self.ask(text,app,CorrelationContext.create())
            self.assertEqual(result.status,ToolResultStatus.SUCCEEDED)
            self.assertFalse(result.output['window_visible_verified'])
        self.assertEqual(self.launched,['notepad','calculator','file_explorer'])

    async def test_denies_hypothetical_negation_and_mismatched_app(self):
        for text,app in [
            ('Never open Notepad','notepad'),
            ('Explain how to open Notepad','notepad'),
            ('What if I asked you to open Notepad?','notepad'),
            ('Open Notepad and delete my files','notepad'),
            ('Open YouTube, then launch Notepad','notepad'),
            ('Open Notepad and Calculator','notepad'),
            ('Open notepad.com','notepad'),
            ('Open Discord','notepad'),
            ('Open Calculator','notepad'),
            ('Run "Notepad"','notepad'),
        ]:
            with self.subTest(text=text):
                got=await self.ask(text,app,CorrelationContext.create())
                self.assertEqual(got.status,ToolResultStatus.DENIED)
        self.assertEqual(self.launched,[])

    async def test_missing_evidence_and_invalid_arguments_fail_closed(self):
        self.assertEqual((await self.ask('Open Notepad',evidence=False)).status,ToolResultStatus.DENIED)
        for args in ({'app':'powershell'},{'app':'notepad','exe':'c:/abc.exe'},{}, {'app':['notepad']}):
            self.assertEqual((await self.ask('Open Notepad',arguments=args)).status,ToolResultStatus.DENIED)
        self.assertFalse(self.launched)

    async def test_turn_replay_protects_duplicate_launch(self):
        a=await self.ask('Open Notepad')
        b=await self.ask('Open Notepad')
        self.assertIs(a,b)
        self.assertEqual(self.launched,['notepad'])
        diff=await self.ask('Open Calculator','calculator')
        self.assertEqual(diff.error_code,'replay_key_conflict')

    async def test_launcher_failure_is_truthful(self):
        self.gateway=CoreDesktopAppGateway(launcher=lambda app: False)
        result=await self.ask('Open Notepad')
        self.assertEqual(result.status,ToolResultStatus.FAILED)
        self.assertEqual(result.error_code,'app_launch_unavailable')
        self.assertFalse(result.output)

    async def test_wrong_turn_binding_does_not_authorize(self):
        trace=CorrelationContext.create()
        req=ToolRequest(trace,'desktop_app','launch',{'app':'notepad'})
        outcome=await self.gateway.execute(req,evidence=ConfirmedUserAction('different_turn','Open Notepad',True,True))
        self.assertEqual(outcome.status,ToolResultStatus.DENIED)
        self.assertFalse(self.launched)


class UnifiedSessionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.launched=[];self.browser=StubBrowser()
        self.session=UnifiedDesktopActionSession(browser=self.browser,advanced=True,bridge_mode=True,
                                                 app_launcher=lambda app:self.launched.append(app) or True)

    async def test_app_action_one_turn_and_binding(self):
        self.session.on_turn_started(4)
        result=await self.session.handle(turn=4,selected_tool='launch_app',source='voice',
                 binding='item_test_4',transcript='Please open Calculator for me',arguments={'app':'calculator'})
        self.assertEqual(result.status,'completed')
        self.assertEqual(result.code,'handoff_not_window_verified')
        self.assertIsNone(await self.session.handle(turn=4,selected_tool='launch_app',source='voice',
                 binding='item_test_4',transcript='Open Calculator',arguments={'app':'calculator'}))
        self.assertEqual(self.launched,['calculator'])
        self.assertFalse(self.browser.calls)

    async def test_browser_tool_unchanged(self):
        self.session.on_turn_started(6)
        result=await self.session.handle(turn=6,selected_tool='browser_action',source='voice',
                binding='item_test_6',transcript='Open YouTube',arguments={'site':'youtube.com','intent':'open'})
        self.assertEqual(result.status,'completed')
        self.assertEqual(len(self.browser.calls),1)
        self.assertFalse(self.launched)

    async def test_invalid_app_request_cannot_drop_to_browser(self):
        self.session.on_turn_started(8)
        result=await self.session.handle(turn=8,selected_tool='launch_app',source='typed',
                binding='typed:8',transcript='Open Notepad',arguments={'app':'powershell'})
        self.assertEqual(result.status,'failed')
        self.assertFalse(self.browser.calls or self.launched)

    async def test_untrusted_browser_and_voice_turn_cannot_launch(self):
        self.session.on_turn_started(10)
        result=await self.session.handle(turn=10,selected_tool='launch_app',source='voice',
                binding='typed:10',transcript='Open Notepad',arguments={'app':'notepad'})
        self.assertEqual(result.status,'failed')
        self.assertFalse(self.launched)

    async def test_old_turn_does_not_launch(self):
        self.session.on_turn_started(11)
        self.assertIsNone(await self.session.handle(turn=10,selected_tool='launch_app',source='typed',
                 binding='typed:10',transcript='Open Notepad',arguments={'app':'notepad'}))
        self.assertFalse(self.launched)


class WiringContracts(unittest.TestCase):
    def test_mode_flag_does_not_change_existing_browser_mode(self):
        script=(ROOT/'scripts/realtime_ab.py').read_text(encoding='utf-8')
        self.assertIn('JARVIS_DESKTOP_APP_PROBE',script)
        self.assertIn('mini-overlap-luna-trim-guided-browser-bridge',script)
        self.assertIn('mini-overlap-luna-trim-guided-unified-desktop',script)

    def test_ui_preserves_transcript_binding_and_selected_tool(self):
        ui=(ROOT/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
        self.assertIn("pending.tool === 'launch_app'",ui)
        self.assertIn("desktopAppRef.current && tool === 'launch_app'",ui)
        self.assertIn('text:input?.turn === pending.turn',ui)

    def test_no_arbitrary_unsafe_os_execution(self):
        content=(ROOT/'core/tools/desktop_apps.py').read_text(encoding='utf-8')
        self.assertNotIn('shell=True',content)
        self.assertNotIn('subprocess.Popen(',content)
        self.assertIn('GetSystemDirectoryW',content)
        self.assertEqual(set(APP_CATALOG),{'notepad','calculator','file_explorer'})

if __name__ == '__main__':
    unittest.main()
