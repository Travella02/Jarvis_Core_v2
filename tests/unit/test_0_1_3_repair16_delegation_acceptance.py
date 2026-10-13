"""Repair16 acceptance runner: isolated env and deterministic Core-bound safety."""
from __future__ import annotations
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch
from core.intelligence import DelegationMode, DelegationStatus
from apps.desktop_luna import DesktopLunaDelegator
from scripts import realtime_ab
from scripts.repair16_delegation_report import summarize

ROOT = Path(__file__).resolve().parents[2]

class LauncherTests(TestCase):
    def launch(self, mode):
        with patch('sys.argv',['realtime_ab.py',mode]), patch.object(realtime_ab.subprocess,'call',return_value=0) as call:
            self.assertEqual(realtime_ab.main(),0)
        args, kwargs=call.call_args
        self.assertEqual(args[0], ['npm','run','desktop'])
        return kwargs['env']
    def test_normal_trim_unmodified_and_never_holds_core_result(self):
        env=self.launch('mini-overlap-luna-trim')
        self.assertEqual(env['JARVIS_REALTIME_OVERLAP_PROBE'],'1')
        self.assertEqual(env['JARVIS_PCM_TRIM_LEADING_SILENCE'],'1')
        self.assertEqual(env['JARVIS_CORE_LUNA_PROBE'],'1')
        self.assertEqual(env['JARVIS_LUNA_RESULT_HOLD_SECONDS'],'0')
        self.assertEqual(env['JARVIS_DECISIONS_SHADOW_PROBE'],'0')
    def test_trimmed_cancel_trial_differs_only_by_result_hold(self):
        baseline=self.launch('mini-overlap-luna-trim')
        trial=self.launch('mini-overlap-luna-trim-cancel-test')
        changed={key for key in set(baseline)|set(trial) if baseline.get(key)!=trial.get(key)}
        self.assertEqual(changed,{'JARVIS_LUNA_RESULT_HOLD_SECONDS'})
        self.assertEqual(trial['JARVIS_LUNA_RESULT_HOLD_SECONDS'],'8')
        self.assertEqual(trial['JARVIS_PCM_TRIM_LEADING_SILENCE'],'1')
    def test_existing_cancel_trial_does_not_suddenly_enable_trim(self):
        env=self.launch('mini-overlap-luna-cancel-test')
        self.assertEqual(env['JARVIS_PCM_TRIM_LEADING_SILENCE'],'0')
        self.assertEqual(env['JARVIS_LUNA_RESULT_HOLD_SECONDS'],'8')
    def test_no_real_action_mode_in_new_trial(self):
        env=self.launch('mini-overlap-luna-trim-cancel-test')
        self.assertEqual(env['JARVIS_REALTIME_TOOL_SELECTION_PROBE'],'0')
        self.assertEqual(env['JARVIS_REALTIME_BUFFERED_TOOL_PROBE'],'0')
        self.assertEqual(env['JARVIS_PARALLEL_SHADOW_PROBE'],'0')
        src=(ROOT/'apps/desktop_luna.py').read_text(encoding='utf-8')
        self.assertIn('mode=DelegationMode.REASONING',src)
        self.assertNotIn('DelegationMode.ACTION',src)

class FakeConversation:
    def __init__(self): self.cancels=[]
    async def cancel_active_turn(self,why): self.cancels.append(why); return True
class FakeCore:
    def __init__(self): self.goals=[]
    async def execute(self,request,*,conversation):
        self.goals.append((request.goal, request.mode))
        return SimpleNamespace(status=DelegationStatus.COMPLETED,text='Verified test response',decision=SimpleNamespace(route_name='core_test'))

class LifecycleTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sent=[];self.core=FakeCore();self.convo=FakeConversation()
        async def notify(item): self.sent.append(item)
        self.luna=DesktopLunaDelegator(orchestrator=self.core,conversation=self.convo,notify=notify,result_hold_seconds=.07)
        # Isolate cancellation timing from the real ~600 ms Windows cue.
        # Live cancel-test mode still plays the actual native notification.
        self._cue_patch = patch('apps.desktop_luna.play_native_hold_cue', return_value='playback_api_completed')
        self._cue_patch.start()
        self.addCleanup(self._cue_patch.stop)
    async def asyncTearDown(self): await self.luna.close()
    async def drain(self):
        for _ in range(40):
            if not self.luna._tasks: return
            await asyncio.sleep(.01)
        self.fail('Core task did not settle')
    async def test_new_question_supersedes_held_core_result(self):
        self.luna.transcript(1,'Analyze reliability')
        self.assertTrue(self.luna.selected(1))
        await asyncio.sleep(.015)
        self.luna.transcript(2,'Now analyze availability')
        self.assertTrue(self.luna.selected(2))
        await self.drain()
        self.assertEqual([item['turn'] for item in self.sent if item['kind']=='core_luna_result'],[2])
        self.assertEqual(self.core.goals, [('Analyze reliability',DelegationMode.REASONING),('Now analyze availability',DelegationMode.REASONING)])
    async def test_sleep_discards_held_result(self):
        self.luna.transcript(1,'Analyze architecture')
        self.luna.selected(1)
        await asyncio.sleep(.015)
        await self.luna.cancel()
        await self.drain()
        self.assertEqual([item for item in self.sent if item['kind']=='core_luna_result'],[])
    async def test_duplicate_core_selection_is_not_executed_twice(self):
        self.luna.transcript(1,'Analyze architecture')
        self.assertTrue(self.luna.selected(1))
        self.assertFalse(self.luna.selected(1))
        await self.drain()
        self.assertEqual(len(self.core.goals),1)
        self.assertEqual(len([item for item in self.sent if item['kind']=='core_luna_result']),1)

class ReportTests(TestCase):
    def test_selection_alone_does_not_count_as_core_execution(self):
        out=summarize(['[Jarvis Tool Probe] turn=2 | tool=ask_luna | phase=selection | dry_run=False\n'])
        self.assertEqual(out['luna_tool_selected'],1)
        self.assertEqual(out['core_started'],0)
        self.assertEqual(out['core_results'],0)
    def test_only_report_counts_and_no_transcripts(self):
        log=['[Jarvis Luna] turn=2 | phase=core_started | authority=core\n',
             '[Jarvis Luna] turn=2 | phase=result | status=completed | route=foo | elapsed_ms=312 | text_chars=82 | authority=core\n',
             '[Jarvis Luna Voice] turn=2 | phase=started | reason=n/a\n',
             '[Jarvis Luna Voice] turn=2 | phase=synthesis_completed | reason=n/a\n',
             '[Jarvis Tool Probe] turn=3 | tool=test_action | phase=selection | dry_run=True\n',
             '[Jarvis Luna Cancel Test] turn=4 | phase=holding_result | seconds=8\n',
             '[Jarvis Luna Cancel Test] turn=4 | phase=stale_result_discarded | voice_delivered=false\n']
        out=summarize(log)
        self.assertEqual(out['core_started'],1)
        self.assertEqual(out['core_results'],1)
        self.assertEqual(out['voice_synthesis_completed'],1)
        self.assertEqual(out['median_core_result_elapsed_ms'],312)
        self.assertEqual(out['action_tool_selected_dry_run'],1)
        self.assertEqual(out['held_result_discarded'],1)
        self.assertNotIn('transcript',out)

if __name__ == '__main__':
    import unittest;unittest.main()
