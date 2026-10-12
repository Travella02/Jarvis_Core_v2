"""0.1.3 Repair6: avoid OFFLINE on incomplete direct answer, recover finished Core failures."""
from __future__ import annotations
import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest
from core.conversation import ConversationContext, ConversationCore, CoreState
from core.intelligence import IntelligenceEvent, IntelligenceEventType, DelegationStatus
from tests.integration.test_conversation_core import FakeProvider, text_turn
from apps.desktop_luna import DesktopLunaDelegator

ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
ENGINE = (ROOT/'core/conversation/engine.py').read_text(encoding='utf-8')
HOST = (ROOT/'apps/desktop_luna.py').read_text(encoding='utf-8')

class DirectAudioSafety(unittest.TestCase):
    def test_direct_failure_recovers_ui_without_claiming_completion(self):
        recovery=APP.split('const recoverIncompleteDirectResponse =',1)[1].split('const fallbackCoreLunaVoice =',1)[0]
        self.assertIn("overlapCandidateStageRef.current !== 'overlap_candidate'",recovery)
        self.assertIn("overlapDecisionRef.current !== 'direct'",recovery)
        self.assertIn("turn !== overlapActiveTurnRef.current",recovery)
        self.assertIn("presenceRef.current !== 'awake'",recovery)
        self.assertIn('overlapGateRef.current?.abort();',recovery)
        self.assertNotIn("abort('candidate_incomplete')",recovery)
        self.assertNotIn("setStateSafely('error'",recovery)
        self.assertIn("setStateSafely('idle','Ready')",recovery)
        self.assertIn('completed_voice_delivered:false',recovery)
        self.assertIn('partial_playback_possible:',recovery)
        self.assertIn("phase:'recoverable_incomplete'",recovery)
    def test_incomplete_event_uses_safe_recovery(self):
        branch=APP.split("if (responseId === overlapCandidateIdRef.current && stage === overlapCandidateStageRef.current)",1)[1].split('if (type ===',1)[0]
        self.assertIn('recoverIncompleteDirectResponse(turn,reason)',branch)
        self.assertNotIn("setStateSafely('error','Candidate answer incomplete')",branch)
        self.assertNotIn("abort('candidate_incomplete')",branch)
        self.assertIn('fallbackCoreLunaVoice(turn,reason)',branch)
    def test_pcm_errors_recover_direct_without_overriding_core_fallback(self):
        self.assertIn("recoverIncompleteDirectResponse(turn,'pcm_'+reason)",APP)
        self.assertIn("recoverIncompleteDirectResponse(turn,'pcm_unavailable')",APP)
        self.assertIn("recoverIncompleteDirectResponse(turn,'remote_stream_unavailable')",APP)
        self.assertIn('!recoverIncompleteDirectResponse(turn,reason)',APP)
    def test_voice_token_policy_not_changed(self):
        selection=APP.split('const requestOverlapResponses =',1)[1].split('const awaitOverlapAudioCommit =',1)[0]
        self.assertIn("output_modalities:['audio'],max_output_tokens:1024",selection)
        corevoice=APP.split('const speakCoreLunaResult =',1)[1].split('const handleRealtimeEvent',1)[0]
        self.assertIn("max_output_tokens:'inf'",corevoice)

class CoreRecovery(unittest.IsolatedAsyncioTestCase):
    async def test_provider_error_then_explicit_recovery_then_new_turn(self):
        provider=FakeProvider([[IntelligenceEvent(IntelligenceEventType.ERROR,detail='temporary')],text_turn('recovered')])
        core=ConversationCore(context=ConversationContext('conv','user'), provider=provider)
        result=await core.submit_voice('first')
        self.assertEqual(result.status,'error')
        self.assertEqual(core.state.state,CoreState.ERROR)
        with self.assertRaises(RuntimeError):
            await core.submit_voice('should not auto retry')
        self.assertTrue(core.recover_idle_after_terminal_failure())
        self.assertEqual(core.state.state,CoreState.LISTENING)
        self.assertFalse(core.recover_idle_after_terminal_failure())
        second=await core.submit_voice('new user request')
        self.assertEqual(second.status,'completed')
        self.assertEqual(second.text,'recovered')
        self.assertEqual(len(provider.contexts),2)
    async def test_never_recover_live_or_sleeping_core(self):
        provider=FakeProvider([])
        core=ConversationCore(context=ConversationContext('conv','user'),provider=provider)
        self.assertFalse(core.recover_idle_after_terminal_failure())
        core.state.transition(CoreState.SLEEPING)
        self.assertFalse(core.recover_idle_after_terminal_failure())
        core.state.transition(CoreState.WAKING)
        core.state.transition(CoreState.LISTENING)
        core.state.transition(CoreState.ERROR)
        core._active_trace=object()
        self.assertFalse(core.recover_idle_after_terminal_failure())
        self.assertEqual(core.state.state,CoreState.ERROR)
    async def test_degraded_terminal_state_recovers_only_on_explicit_new_attempt(self):
        core=ConversationCore(context=ConversationContext('conv','user'),provider=FakeProvider([]))
        core.state.transition(CoreState.DEGRADED)
        self.assertTrue(core.recover_idle_after_terminal_failure())
        self.assertEqual(core.state.state,CoreState.LISTENING)

class LoggingContracts(unittest.TestCase):
    def test_luna_recovery_is_inside_serialized_provider_critical_section(self):
        section=HOST.split('async with self._provider_lock:',1)[1].split('result = await self.orchestrator.execute',1)[0]
        self.assertIn('recover_idle_after_terminal_failure',section)
        self.assertIn('phase=core_recovered',section)
        self.assertIn('self._executing_turn = turn',section)
    def test_runtime_error_is_not_assumed_network_failure(self):
        self.assertIn('category = "core_busy"',HOST)
        self.assertIn('"core_not_ready"',HOST)
        self.assertNotIn("I couldn't reach Luna for that request.",HOST)

if __name__ == '__main__':unittest.main()
