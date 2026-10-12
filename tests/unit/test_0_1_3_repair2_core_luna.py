"""0.1.3 Repair2 real-Core Luna reasoning, lifecycle/cancel/fail-closed contracts."""
from __future__ import annotations
import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest
from apps.desktop_luna import DesktopLunaDelegator
from core.intelligence import DelegationMode, DelegationStatus

ROOT = Path(__file__).resolve().parents[2]

class MockConversation:
    def __init__(self):
        self.cancels = []
    async def cancel_active_turn(self, reason):
        self.cancels.append(reason)
        return True

class MockOrchestrator:
    def __init__(self, *, status=DelegationStatus.COMPLETED, answer='Luna verified: 42', wait=None):
        self.calls=[]
        self.status=status
        self.answer=answer
        self.wait=wait
    async def execute(self, request, *, conversation):
        self.calls.append((request,conversation))
        if self.wait is not None: await self.wait.wait()
        return SimpleNamespace(status=self.status,text=self.answer,decision=SimpleNamespace(route_name='default'))

class CoreLunaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sent=[]
        async def notify(msg): self.sent.append(msg)
        self.notify=notify
        self.conversation=MockConversation()
        self.orchestrator=MockOrchestrator()
        self.luna=DesktopLunaDelegator(orchestrator=self.orchestrator,conversation=self.conversation,notify=notify,transcript_timeout=.02)
    async def asyncTearDown(self):
        await self.luna.close()
    async def drain(self):
        for _ in range(30):
            if not self.luna._tasks: return
            await asyncio.sleep(.01)
    async def test_real_reasoning_uses_confirmed_transcript_not_model_tool_arguments(self):
        self.luna.new_turn(1)
        self.luna.transcript(1,'Please analyze the design of my app')
        self.assertTrue(self.luna.selected(1))
        await self.drain()
        self.assertEqual(self.orchestrator.calls[0][0].goal,'Please analyze the design of my app')
        self.assertEqual(self.orchestrator.calls[0][0].mode,DelegationMode.REASONING)
        self.assertIs(self.orchestrator.calls[0][1],self.conversation)
        self.assertEqual(self.sent[0]['status'],'completed')
        self.assertIn('verified',self.sent[0]['text'])
    async def test_late_duplicate_selection_is_still_rejected(self):
        self.luna.new_turn(1)
        self.luna.transcript(1,'Only once')
        self.assertTrue(self.luna.selected(1))
        await self.drain()
        self.assertFalse(self.luna.selected(1))
        self.assertEqual(len(self.orchestrator.calls),1)

    async def test_transcript_after_tool_decision(self):
        self.luna.new_turn(1)
        self.assertTrue(self.luna.selected(1))
        await asyncio.sleep(0)
        self.luna.transcript(1,'Late but valid user transcript')
        await self.drain()
        self.assertEqual(len(self.orchestrator.calls),1)
        self.assertEqual(self.sent[0]['turn'],1)
    async def test_no_transcript_never_executes(self):
        self.luna.new_turn(1)
        self.assertTrue(self.luna.selected(1))
        await self.drain()
        self.assertEqual(self.orchestrator.calls,[])
        self.assertEqual(self.sent[0]['status'],'unavailable')
    async def test_duplicate_tool_event_ignored(self):
        self.luna.new_turn(1)
        self.assertTrue(self.luna.selected(1))
        self.assertFalse(self.luna.selected(1))
        self.luna.transcript(1,'Design it')
        await self.drain()
        self.assertEqual(len(self.orchestrator.calls),1)
    async def test_stale_task_never_speaks(self):
        wait=asyncio.Event()
        self.orchestrator.wait=wait
        self.luna.new_turn(1)
        self.luna.transcript(1,'First analysis')
        self.assertTrue(self.luna.selected(1))
        await asyncio.sleep(.02)
        self.luna.new_turn(2)
        self.luna.transcript(2,'Second analysis')
        self.assertTrue(self.luna.selected(2))
        await asyncio.sleep(.02)
        self.assertGreaterEqual(len(self.conversation.cancels),1)
        wait.set()
        await self.drain()
        self.assertEqual([r['turn'] for r in self.sent],[2])
    async def test_cancel_before_transcript(self):
        self.luna.new_turn(1)
        self.assertTrue(self.luna.selected(1))
        await self.luna.cancel()
        await self.drain()
        self.assertFalse(self.orchestrator.calls)
        self.assertFalse(self.sent)
    async def test_failed_luna_has_truthful_output(self):
        self.orchestrator.status=DelegationStatus.FAILED
        self.luna.new_turn(1)
        self.luna.transcript(1,'analyze this')
        self.luna.selected(1)
        await self.drain()
        self.assertEqual(self.sent[0]['status'],'failed')
        self.assertIn('couldn\'t', self.sent[0]['text'])
    async def test_close_discards_late_completion(self):
        wait=asyncio.Event()
        self.orchestrator.wait=wait
        self.luna.new_turn(1)
        self.luna.transcript(1,'something')
        self.luna.selected(1)
        await asyncio.sleep(.01)
        await self.luna.close()
        wait.set()
        await asyncio.sleep(.05)
        self.assertFalse(self.sent)
    async def test_response_length_bounded(self):
        self.orchestrator.answer='A'*5000
        self.luna.new_turn(1)
        self.luna.transcript(1,'question')
        self.luna.selected(1)
        await self.drain()
        self.assertEqual(len(self.sent[0]['text']),3000)

class SourceContracts(unittest.TestCase):
    def test_opt_in_no_changes_to_existing_modes(self):
        source=(ROOT/'scripts/realtime_ab.py').read_text(encoding='utf-8')
        self.assertIn('"mini-overlap-luna"',source)
        self.assertIn('luna_probe = sys.argv[1] == "mini-overlap-luna"',source)
        self.assertIn('"JARVIS_CORE_LUNA_PROBE"',source)
        cfg=(ROOT/'providers/voice_frontend/openai_realtime/config.py').read_text(encoding='utf-8')
        self.assertIn('core_luna_probe: bool = False',cfg)
    def test_single_response_ownership_and_no_early_audio(self):
        app=(ROOT/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
        self.assertIn("if (realLuna)",app)
        self.assertIn("overlapGateRef.current?.abort()",app)
        self.assertIn("phase:'selection',dry_run:!realLuna",app)
        self.assertIn("if (epoch !== overlapEpochRef.current",app)
        self.assertIn('turn !== overlapActiveTurnRef.current',app)
        self.assertIn("jarvis_stage:'core_luna_voice'",app)
        self.assertIn("conversation:'none'",app)
        self.assertIn('tools:[],tool_choice:\'none\'',app)
        self.assertIn("presenceRef.current !== 'awake'",app)
    def test_no_luna_action_execution(self):
        module=(ROOT/'apps/desktop_luna.py').read_text(encoding='utf-8')
        self.assertIn('mode=DelegationMode.REASONING',module)
        self.assertNotIn('DelegationMode.ACTION',module)
        self.assertIn('self._texts.get(turn',module)
        host=(ROOT/'apps/desktop_alpha.py').read_text(encoding='utf-8')
        self.assertIn('if self.config.core_luna_probe:',host)
        self.assertIn('live_luna = self._luna is not None',host)

if __name__ == '__main__': unittest.main()
