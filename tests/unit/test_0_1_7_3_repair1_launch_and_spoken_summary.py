"""0.1.7.3 Repair1: no accidental launch from in-app requests; brief grounded TTS."""
from __future__ import annotations
import asyncio
import unittest
from pathlib import Path
from unittest.mock import patch

from apps.desktop_unified_actions import UnifiedDesktopActionSession
from core.tools.desktop_apps import CoreDesktopAppGateway
from core.tools.app_discovery import InstalledApp, InstalledAppInventory
from core.common.ids import CorrelationContext
from core.tools import ToolRequest, ToolResultStatus
from core.tools.gateway import ConfirmedUserAction
from core.tools.background_browser import compact_page_observation_for_speech

ROOT=Path(__file__).resolve().parents[2]

class LaunchIntentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.launches=[]
        inv=InstalledAppInventory(discover=lambda:[
            InstalledApp('Notepad','system','notepad.exe','system'),
            InstalledApp('Discord','shortcut','C:/Start/Discord.lnk','start_menu'),
            InstalledApp('Spotify','shortcut','C:/Start/Spotify.lnk','start_menu'),
        ], auto_start=False)
        inv._refresh()
        self.gateway=CoreDesktopAppGateway(inventory=inv,dynamic=True,
            launcher=lambda app:self.launches.append(app) or True)

    async def check(self,text,app):
        trace=CorrelationContext.create()
        return await self.gateway.execute(ToolRequest(trace,'desktop_app','launch',{'app':app}),
            evidence=ConfirmedUserAction(trace.turn_id,text,True,True))

    async def test_navigation_references_are_not_authorized_app_launches(self):
        cases=[
            ('Play the file button in the open Notepad','notepad'),
            ('Click the File menu in the open Notepad','notepad'),
            ('Tap the Open button in Discord','discord'),
            ('Scroll down and open Spotify settings','spotify'),
            ('Click the open Notepad window','notepad'),
            ('I am already in the open Notepad','notepad'),
            ('Could you select the menu in open Discord','discord'),
        ]
        for text,app in cases:
            with self.subTest(text=text):
                result=await self.check(text,app)
                self.assertEqual(result.status,ToolResultStatus.DENIED)
                self.assertEqual(result.error_code,'unverified_user_intent')
        self.assertEqual(self.launches,[])

    async def test_legitimate_natural_app_launches_still_authorized(self):
        cases=[('Please open Notepad for me','notepad'),
               ('Could you open Discord for me','discord'),
               ('Could you bring up Spotify, Jarvis?','spotify')]
        for text,app in cases:
            with self.subTest(text=text):
                result=await self.check(text,app)
                self.assertEqual(result.status,ToolResultStatus.SUCCEEDED)
        self.assertEqual(self.launches,['notepad','discord','spotify'])

    async def test_misrouted_unified_session_never_launches(self):
        session=UnifiedDesktopActionSession(app_launcher=lambda app:self.launches.append(app) or True,
            universal_apps=False)
        session.on_turn_started(11)
        with patch('core.tools.foreground_safety.protect_existing_desktop_action',return_value=None):
            result=await session.handle(turn=11,selected_tool='launch_app',source='voice',
                binding='item_confirmed_11',transcript='Play the file button in the open Notepad',
                arguments={'app':'notepad'})
        self.assertEqual(result.status,'failed')
        self.assertEqual(result.code,'unverified_user_intent')
        self.assertEqual(self.launches,[])

class ShortObservationTests(unittest.TestCase):
    def test_multilingual_page_not_read_in_full(self):
        raw=('Isolated browser at example.org. Page title: Example Domain. Visible page text: '
             'This domain is for use in documentation examples without needing permission. '
             'This is not a service; avoid relying on it for testing and monitoring purposes. '
             'هذا النطاق مُخصص للاستخدام في أمثلة التوثيق دون الحاجة إلى إذن. '
             '该域名仅用于文档示例，无需获得许可。 No action was taken.')
        spoken=compact_page_observation_for_speech(raw)
        self.assertIn('example.org',spoken)
        self.assertIn('Example Domain',spoken)
        self.assertIn('documentation',spoken)
        self.assertNotIn('هذا',spoken)
        self.assertNotIn('该域名',spoken)
        self.assertLessEqual(len(spoken),235)

    def test_factual_first_sentence_is_preserved_not_invented(self):
        raw=('Isolated browser at docs.example.org. Page title: Release Notes. '
             'Visible page text: Version 2 is available. This second sentence should not be spoken. No action was taken.')
        spoken=compact_page_observation_for_speech(raw)
        self.assertIn('Version 2 is available.',spoken)
        self.assertNotIn('second sentence',spoken)
        self.assertIn('Release Notes',spoken)

    def test_unknown_observation_shape_is_bounded(self):
        self.assertLessEqual(len(compact_page_observation_for_speech('word'*300)),235)

    def test_template_documents_actual_flags(self):
        env=(ROOT/'.env.example').read_text('utf-8')
        for key in ('JARVIS_TERRA_BACKGROUND_NATIVE_INSPECT=1',
                    'JARVIS_TERRA_BACKGROUND_DIRECT_LINKS=0',
                    'JARVIS_TERRA_BACKGROUND_IDLE_TTL=120'):
            self.assertIn(key,env)

if __name__=='__main__':unittest.main()
