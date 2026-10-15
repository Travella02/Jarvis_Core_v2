"""Repair16 Repair1: isolated audible cue and fail-closed Core-result cancellation."""
from __future__ import annotations

import asyncio
import io
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from unittest import IsolatedAsyncioTestCase, TestCase

from apps.desktop_luna import DesktopLunaDelegator
from core.intelligence import DelegationStatus

ROOT = Path(__file__).resolve().parents[2]


class FakeCore:
    async def execute(self, request, *, conversation):
        return SimpleNamespace(
            status=DelegationStatus.COMPLETED,
            text='Fake Core result that must never leak during cancellation',
            decision=SimpleNamespace(route_name='primary'),
        )


class FakeConversation:
    async def cancel_active_turn(self, reason):
        return True


class CueTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # These three lifecycle tests verify cancellation timing, not speakers.
        # Real WAV playback here used to beep during `unittest discover` on
        # Windows; the separate native audio test already mocks winsound.
        self._sound = patch('apps.desktop_luna.play_native_hold_cue', return_value='playback_api_completed')
        self._sound.start()
        self.addCleanup(self._sound.stop)

    async def make_delegator(self, hold):
        sent = []
        recorded = io.StringIO()
        async def notify(message):
            sent.append(message)
        delegate = DesktopLunaDelegator(
            orchestrator=FakeCore(),
            conversation=FakeConversation(),
            notify=notify,
            result_hold_seconds=hold,
        )
        return delegate, sent, recorded

    async def wait_until(self, callback):
        for _ in range(60):
            if callback():
                return
            await asyncio.sleep(.005)
        self.fail('timed out waiting for provider test phase')

    async def test_new_question_discards_held_result_and_prints_pass(self):
        delegate, sent, output = await self.make_delegator(.09)
        try:
            with redirect_stdout(output):
                delegate.transcript(1, 'Complex task')
                self.assertTrue(delegate.selected(1))
                await self.wait_until(lambda: any(m['kind'] == 'core_luna_cancel_hold' for m in sent))
                self.assertEqual([m['turn'] for m in sent if m['kind'] == 'core_luna_cancel_hold'], [1])
                delegate.new_turn(2)
                await asyncio.sleep(.12)
            self.assertFalse(any(m['kind'] == 'core_luna_result' and m['turn'] == 1 for m in sent))
            self.assertIn('phase=stale_result_discarded', output.getvalue())
            self.assertIn('outcome=PASS | reason=new_turn | result_released=false', output.getvalue())
            self.assertNotIn('phase=releasing_current_result', output.getvalue())
        finally:
            await delegate.close()

    async def test_sleep_discards_held_result_and_prints_pass(self):
        delegate, sent, output = await self.make_delegator(.09)
        try:
            with redirect_stdout(output):
                delegate.transcript(1, 'Complex task')
                self.assertTrue(delegate.selected(1))
                await self.wait_until(lambda: any(m['kind'] == 'core_luna_cancel_hold' for m in sent))
                await delegate.cancel()
                await asyncio.sleep(.12)
            self.assertFalse(any(m['kind'] == 'core_luna_result' for m in sent))
            self.assertIn('outcome=PASS | reason=sleep_or_cancel | result_released=false', output.getvalue())
        finally:
            await delegate.close()

    async def test_hold_expiry_is_not_falsely_reported_as_success(self):
        delegate, sent, output = await self.make_delegator(.025)
        try:
            with redirect_stdout(output):
                delegate.transcript(1, 'Complex task')
                self.assertTrue(delegate.selected(1))
                await self.wait_until(lambda: any(m['kind'] == 'core_luna_result' for m in sent))
            self.assertIn('outcome=NOT_TESTED | reason=hold_expired | result_released=true', output.getvalue())
            self.assertNotIn('outcome=PASS', output.getvalue())
            self.assertEqual(sum(m['kind'] == 'core_luna_result' for m in sent), 1)
        finally:
            await delegate.close()

    async def test_normal_mode_never_emits_test_cue(self):
        delegate, sent, _ = await self.make_delegator(0)
        try:
            delegate.transcript(1, 'Complex task')
            self.assertTrue(delegate.selected(1))
            await self.wait_until(lambda: any(m['kind'] == 'core_luna_result' for m in sent))
            self.assertEqual([m['kind'] for m in sent], ['core_luna_result'])
        finally:
            await delegate.close()


class RendererContracts(TestCase):
    def test_cue_uses_local_audio_not_ai_or_control_authority(self):
        tone = (ROOT / 'apps/desktop/ui/src/lunaCancelCue.ts').read_text(encoding='utf-8')
        app = (ROOT / 'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
        self.assertIn('new AudioContext()', tone)
        self.assertIn('createOscillator()', tone)
        self.assertIn("payload.kind === 'core_luna_cancel_hold'", app)
        self.assertIn('TEST MODE · INTERRUPT NOW (8 SEC)', app)
        self.assertIn("payload.kind === 'core_luna_cancel_hold_ended'", app)
        self.assertNotIn('response.create', tone)
        self.assertNotIn('core_luna_result', tone)

    def test_launch_hold_stays_eight_seconds_and_opt_in(self):
        from scripts import realtime_ab
        from unittest.mock import patch
        for mode, expected in [('mini-overlap-luna-trim', '0'),
                               ('mini-overlap-luna-trim-cancel-test', '8')]:
            with patch('sys.argv', ['realtime_ab.py', mode]), patch.object(realtime_ab.subprocess, 'call', return_value=0) as call:
                self.assertEqual(realtime_ab.main(), 0)
            env = call.call_args.kwargs['env']
            self.assertEqual(env['JARVIS_LUNA_RESULT_HOLD_SECONDS'], expected)
            self.assertEqual(env['JARVIS_PCM_TRIM_LEADING_SILENCE'], '1')
