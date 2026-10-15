"""0.1.5.3 Repair1: trusted action acknowledgment and negative voice outcomes.

No network, sound, real browser or model requests.
"""
import asyncio
from pathlib import Path
import unittest

from providers.voice_frontend.openai_realtime.webrtc import BrowserRealtimeRelay

ROOT=Path(__file__).resolve().parents[2]


class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def test_trusted_action_result_is_delivered_to_renderer(self):
        relay=BrowserRealtimeRelay()
        await relay.notify_desktop({'kind':'core_tool_result','turn':4,'status':'failed',
                                    'text':'This website is not approved yet.'})
        event=await asyncio.wait_for(relay.outgoing().__anext__(),0.2)
        self.assertEqual(event['kind'],'core_tool_result')
        self.assertEqual(event['turn'],4)
        self.assertEqual(event['status'],'failed')

    async def test_luna_result_remains_forwarded(self):
        relay=BrowserRealtimeRelay()
        await relay.notify_desktop({'kind':'core_luna_result','turn':8,'status':'completed','text':'answer'})
        self.assertEqual((await asyncio.wait_for(relay.outgoing().__anext__(),0.2))['kind'],'core_luna_result')

    async def test_arbitrary_core_events_are_not_forwarded(self):
        relay=BrowserRealtimeRelay()
        await relay.notify_desktop({'kind':'untrusted_injected_message','turn':5})
        self.assertTrue(relay._outgoing.empty())


class UIContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui=(ROOT/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf8')
        cls.host=(ROOT/'apps/desktop_alpha.py').read_text(encoding='utf8')

    def test_success_is_silent_failure_is_audible(self):
        section=self.ui.split("} else if (payload.kind === 'core_tool_result')",1)[1].split(
            "} else if (payload.kind === 'core_luna_result')",1)[0]
        self.assertIn('if (completed) {',section)
        self.assertIn("setStateSafely('idle', 'Ready')",section)
        self.assertIn('announceActionProblem(turn,status,message)',section)
        self.assertNotIn('speakCoreLunaResult(payload)',section)

    def test_failure_uses_verified_result_voice_no_new_tools(self):
        section=self.ui.split('  const announceActionProblem =',1)[1].split('  // A model selecting',1)[0]
        self.assertIn("speakCoreLunaResult({turn, status, origin:'tool', text:safeMessage})",section)
        self.assertIn("phase:'unavailable'",section)
        speech=self.ui.split('  const speakCoreLunaResult =',1)[1].split('  const announceActionProblem =',1)[0]
        self.assertIn("conversation:'none'",speech)
        self.assertIn("tools:[],tool_choice:'none'",speech)
        self.assertIn('Core reported a failure, communicate that failure accurately',speech)

    def test_timeout_unknown_not_false_failure(self):
        section=self.ui.split('  const settlePendingOverlapAction =',1)[1].split('  const settlePendingOverlapDirect =',1)[0]
        self.assertIn("announceActionProblem(pending.turn,'unknown'",section)
        self.assertIn('could not confirm whether',section)
        self.assertIn('Never automatically replay it',section)

    def test_only_core_result_can_settle_same_turn(self):
        section=self.ui.split("} else if (payload.kind === 'core_tool_result')",1)[1].split(
            "} else if (payload.kind === 'core_luna_result')",1)[0]
        for marker in ('awaiting.turn === turn','awaiting.epoch === overlapEpochRef.current',
                       'turn === overlapActiveTurnRef.current',"presenceRef.current === 'awake'",'overlapAwaitingActionResultRef.current = null'):
            self.assertIn(marker,section)
        self.assertIn("kind:'desktop_action_feedback'",section)
        self.assertIn("completed ? 'completed' : (payload.status === 'failed' ? 'failed' : 'unknown')",section)

    def test_no_new_extra_chat_route(self):
        src=self.ui.split('  const settlePendingOverlapDirect =',1)[1]
        self.assertIn('settlePendingOverlapDirect()',src)
        self.assertIn('overlapDecisionRef.current === \'direct\'',src)

if __name__=='__main__': unittest.main()
