"""0.1.3 Repair5 deterministic late-result quarantine and launch isolation."""
from __future__ import annotations
import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from apps.desktop_luna import DesktopLunaDelegator
from core.intelligence import DelegationStatus
from providers.voice_frontend.openai_realtime.config import OpenAIRealtimeConfig
ROOT=Path(__file__).resolve().parents[2]

class FakeConversation:
    def __init__(self):self.cancels=[]
    async def cancel_active_turn(self, reason):self.cancels.append(reason);return True

class FakeOrchestrator:
    def __init__(self):self.calls=[]
    async def execute(self,request,*,conversation):
        self.calls.append(request.goal)
        return SimpleNamespace(status=DelegationStatus.COMPLETED,text='Core-verified answer.',decision=SimpleNamespace(route_name='primary'))

class HoldTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sent=[];self.core=FakeOrchestrator();self.conversation=FakeConversation()
        async def notify(msg):self.sent.append(msg)
        self.luna=DesktopLunaDelegator(orchestrator=self.core,conversation=self.conversation,notify=notify,result_hold_seconds=.09)
    async def asyncTearDown(self):await self.luna.close()
    async def wait_for_core(self):
        for _ in range(50):
            if self.core.calls:return
            await asyncio.sleep(.003)
        self.fail('Core did not run')
    async def wait_for_finish(self):
        for _ in range(70):
            if not self.luna._tasks:return
            await asyncio.sleep(.005)
        self.fail('Luna task did not finish')
    async def test_new_user_turn_drops_held_verified_result(self):
        self.luna.transcript(1,'First complex question');self.assertTrue(self.luna.selected(1))
        await self.wait_for_core()
        await asyncio.sleep(.02)
        self.luna.new_turn(2)
        await self.wait_for_finish()
        self.assertEqual(self.sent,[])
        self.assertEqual(self.core.calls,['First complex question'])
    async def test_new_core_request_does_not_wait_for_old_hold(self):
        self.luna.transcript(1,'First');self.luna.selected(1)
        await self.wait_for_core()
        await asyncio.sleep(.02)
        self.luna.transcript(2,'Second');self.luna.selected(2)
        for _ in range(20):
            if len(self.core.calls)==2:break
            await asyncio.sleep(.002)
        self.assertEqual(self.core.calls,['First','Second'])
        await self.wait_for_finish()
        self.assertEqual([m['turn'] for m in self.sent],[2])
    async def test_sleep_drops_held_verified_result(self):
        self.luna.transcript(1,'First complex question');self.luna.selected(1)
        await self.wait_for_core();await asyncio.sleep(.02)
        await self.luna.cancel()
        await self.wait_for_finish()
        self.assertFalse(self.sent)
    async def test_no_interruption_releases_once(self):
        self.luna.transcript(1,'First complex question');self.luna.selected(1)
        await self.wait_for_finish()
        self.assertEqual(len(self.sent),1)
        self.assertEqual(self.sent[0]['turn'],1)
        self.assertIn('Core-verified',self.sent[0]['text'])
    async def test_duplicate_selection_cannot_bypass_hold(self):
        self.luna.transcript(1,'Original');self.assertTrue(self.luna.selected(1))
        self.assertFalse(self.luna.selected(1))
        await self.wait_for_finish()
        self.assertEqual(self.core.calls,['Original'])
        self.assertEqual(len(self.sent),1)

class ConfigContracts(unittest.TestCase):
    def test_hold_disabled_by_default(self):
        cfg=OpenAIRealtimeConfig.from_env({'OPENAI_API_KEY':'sk-fake'})
        self.assertEqual(cfg.luna_result_hold_seconds,0)
    def test_hold_opt_in(self):
        cfg=OpenAIRealtimeConfig.from_env({'JARVIS_CORE_LUNA_PROBE':'1','JARVIS_LUNA_RESULT_HOLD_SECONDS':'8'})
        self.assertEqual(cfg.luna_result_hold_seconds,8)
    def test_hold_rejected_without_luna(self):
        with self.assertRaises(ValueError):
            OpenAIRealtimeConfig.from_env({'JARVIS_LUNA_RESULT_HOLD_SECONDS':'8'})
    def test_hold_rejects_bad_values(self):
        for value in ('21','-1','nan','inf','bogus'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                OpenAIRealtimeConfig.from_env({'JARVIS_CORE_LUNA_PROBE':'1','JARVIS_LUNA_RESULT_HOLD_SECONDS':value})
    def test_normal_luna_mode_has_no_delay(self):
        s=(ROOT/'scripts/realtime_ab.py').read_text(encoding='utf-8')
        self.assertIn('"8" if luna_cancel_test else "0"',s)
        self.assertIn('mini-overlap-luna-cancel-test',s)
        self.assertIn("luna_probe = luna_probe or luna_cancel_test",s)
    def test_no_audio_pipeline_change(self):
        s=(ROOT/'apps/desktop_luna.py').read_text(encoding='utf-8')
        self.assertIn('if self._closed or turn != self.current_turn:',s)
        self.assertIn('phase=stale_result_discarded',s)
        self.assertIn('phase=holding_result',s)
        self.assertNotIn('DelegationMode.ACTION',s)

if __name__=='__main__':unittest.main()
