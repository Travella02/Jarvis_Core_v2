"""0.1.5.2 Repair2: natural authorized actions + bounded UI lifecycle."""
from pathlib import Path
import unittest
from apps.desktop_actions import DesktopActionSession

ROOT = Path(__file__).resolve().parents[2]

class NaturalActionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.opened = []
        self.session = DesktopActionSession(launcher=lambda url: self.opened.append(url) or True)

    async def check(self, text, expected):
        self.session.on_turn_started(self.session.active_turn + 1)
        turn = self.session.active_turn
        result = await self.session.handle(turn=turn,selected_tool='test_action',
            source='voice',binding=f'item_voice{turn}',transcript=text)
        self.assertIsNotNone(result)
        self.assertEqual(result.status, expected, text)

    async def test_go_ahead_variants_are_verified_from_user_evidence(self):
        for phrase in (
            'Go ahead and open YouTube',
            'Hey go ahead and open YouTube',
            'Hey Jarvis, go ahead and open YouTube for me',
            'Jarvis, can you go ahead and open YouTube?',
            'Could you please go ahead and launch youtube.com for me?',
        ):
            await self.check(phrase, 'completed')
        self.assertEqual(self.opened, ['https://www.youtube.com/'] * 5)

    async def test_conditional_negated_compound_quoted_and_other_site_still_denied(self):
        for phrase in (
            'Go ahead and open Google',
            'Go ahead and open YouTube and Gmail',
            'Do not go ahead and open YouTube',
            'If you are ready, go ahead and open YouTube',
            'Somebody said go ahead and open YouTube',
            'Will you go ahead and open YouTube if I say yes?',
            'Go ahead and open https://youtube.com/watch?v=abc',
        ):
            await self.check(phrase, 'failed')
        self.assertFalse(self.opened)

    async def test_duplicate_action_still_never_executes_twice(self):
        self.session.on_turn_started(1)
        first = await self.session.handle(turn=1,selected_tool='test_action',
            source='voice',binding='item_voice1',transcript='Go ahead and open YouTube')
        second = await self.session.handle(turn=1,selected_tool='test_action',
            source='voice',binding='item_voice1',transcript='Go ahead and open YouTube')
        self.assertEqual(first.status,'completed')
        self.assertIsNone(second)
        self.assertEqual(len(self.opened),1)

class ActionUIContractTests(unittest.TestCase):
    def setUp(self):
        self.ui=(ROOT/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
        self.host=(ROOT/'apps/desktop_alpha.py').read_text(encoding='utf-8')

    def test_action_dispatch_arms_watchdog_before_core_message(self):
        start=self.ui.index('  const settlePendingOverlapAction =')
        end=self.ui.index('  const settlePendingOverlapDirect =',start)
        part=self.ui[start:end]
        self.assertLess(part.index('overlapAwaitingActionResultRef.current = {turn:pending.turn,epoch:pending.epoch}'),
                        part.index("sendControlMessage({kind:'desktop_action_request'"))
        self.assertIn('}, 5000);',part)
        self.assertIn('I could not confirm the browser result.',part)
        self.assertIn("setStateSafely('idle', 'Ready')",part)
        self.assertIn('I will not retry automatically',part)

    def test_core_response_only_settles_matching_action_and_is_silent(self):
        start=self.ui.index("} else if (payload.kind === 'core_tool_result')")
        end=self.ui.index("} else if (payload.kind === 'core_luna_result')",start)
        part=self.ui[start:end]
        for fragment in ('awaiting.turn === turn','awaiting.epoch === overlapEpochRef.current',
                         'turn === overlapActiveTurnRef.current',
                         'overlapAwaitingActionResultRef.current = null',
                         "setStateSafely('idle', 'Ready')",'spoken:false'):
            self.assertIn(fragment,part)
        self.assertNotIn('speakCoreLunaResult',part)

    def test_cancelling_turn_disarms_watchdog(self):
        start=self.ui.index('  const cancelOverlap =')
        end=self.ui.index('  const silenceRealtimeOutput =',start)
        part=self.ui[start:end]
        self.assertIn('window.clearTimeout(overlapActionResultTimerRef.current)',part)
        self.assertIn('overlapAwaitingActionResultRef.current = null',part)

    def test_ui_acknowledgment_is_only_telemetry_never_execution(self):
        start=self.host.index('if kind == "desktop_action_feedback"')
        end=self.host.index('if kind == "desktop_user"',start)
        part=self.host[start:end]
        self.assertIn('[Jarvis Action UI]',part)
        self.assertNotIn('self._action_session.handle(',part)

if __name__=='__main__': unittest.main()
