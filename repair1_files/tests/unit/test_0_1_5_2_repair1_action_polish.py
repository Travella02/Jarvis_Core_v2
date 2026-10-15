"""0.1.5.2 Repair1: polite user commands and visible-action completion contract."""
from pathlib import Path
import asyncio
import unittest
from unittest.mock import patch

from apps.desktop_actions import DesktopActionSession

ROOT = Path(__file__).resolve().parents[2]

class PoliteActionAuthorization(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.opened = []
        self.s = DesktopActionSession(launcher=lambda url: self.opened.append(url) or True)
        self.s.on_turn_started(1)

    async def execute(self, text, *, turn=1, source='voice'):
        return await self.s.handle(turn=turn, selected_tool='test_action',
            source=source, binding='item_voice123' if source == 'voice' else f'typed:{turn}', transcript=text)

    async def test_polite_direct_requests_work_without_model_authority(self):
        for text in (
            'Jarvis, can you open YouTube for me?',
            'Jervis, could you please open YouTube for me?',
            'Hey Jarvis please open youtube please',
            'Would you open YouTube?',
            'Please launch youtube.com for me.',
            'Open YouTube',
        ):
            self.s.on_turn_started(self.s.active_turn+1)
            result = await self.execute(text,turn=self.s.active_turn)
            self.assertEqual(result.status, 'completed', text)
        self.assertEqual(self.opened, ['https://www.youtube.com/']*6)

    async def test_open_google_and_unsafe_requests_remain_denied(self):
        for text in (
            'Open Google',
            'Jarvis, do not open YouTube',
            'Jarvis, can you NOT open YouTube for me?',
            'What does “can you open YouTube for me” mean?',
            'Can you open YouTube and my bank?',
            'If I asked you to open YouTube, would you?',
            'My friend says: can you open YouTube for me?',
            'Open https://www.youtube.com/anything',
        ):
            self.s.on_turn_started(self.s.active_turn+1)
            result=await self.execute(text,turn=self.s.active_turn)
            self.assertEqual(result.status,'failed',text)
        self.assertEqual(self.opened,[])

    async def test_polite_request_does_not_relax_missing_evidence(self):
        r=await self.s.handle(turn=1,selected_tool='test_action',source='voice',binding='',
             transcript='Jarvis, can you open YouTube for me?')
        self.assertEqual(r.status,'failed')
        self.assertFalse(self.opened)

    async def test_polite_request_keeps_same_turn_replay_guard(self):
        results=await asyncio.gather(self.execute('Jarvis, can you open YouTube for me?'),
                                     self.execute('Jarvis, can you open YouTube for me?'))
        self.assertEqual(sum(r is not None for r in results),1)
        self.assertEqual(len(self.opened),1)

class UserExperienceContracts(unittest.TestCase):
    def test_visible_actions_settle_to_ready_without_voice_generation(self):
        text=(ROOT/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
        start=text.index("} else if (payload.kind === 'core_tool_result')")
        end=text.index("} else if (payload.kind === 'core_luna_result')",start)
        action=text[start:end]
        self.assertIn("turn === overlapActiveTurnRef.current",action)
        self.assertIn("overlapDecisionRef.current === 'tool'",action)
        self.assertIn("setCaption(completed ? '' :",action)
        self.assertIn("setStateSafely('idle', 'Ready')",action)
        self.assertNotIn('speakCoreLunaResult',action)
        self.assertIn("spoken:false",action)

    def test_legacy_cue_timing_suite_mocks_real_playback(self):
        text=(ROOT/'tests/unit/test_0_1_3_repair16_repair1_cue.py').read_text(encoding='utf-8')
        self.assertIn("patch('apps.desktop_luna.play_native_hold_cue'", text)
        self.assertIn('self.addCleanup(self._sound.stop)', text)

if __name__ == '__main__': unittest.main()
