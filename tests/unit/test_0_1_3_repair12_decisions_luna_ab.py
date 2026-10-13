"""Repair12: Core/Luna comparison is observational; model classification is never a permission."""
from __future__ import annotations

import asyncio
import json
from unittest import mock
from scripts import realtime_ab
from pathlib import Path
import unittest

import httpx

from providers.intelligence.openai.decisions_shadow import DecisionsShadowProbe
from scripts.repair12_latency_report import parse_log, compute_summary

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = (ROOT / 'scripts/realtime_ab.py').read_text(encoding='utf-8')
HOST = (ROOT / 'apps/desktop_alpha.py').read_text(encoding='utf-8')
RENDERER = (ROOT / 'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')


def result(route='direct', sleep=.01, memory=.01):
    return {'answers': [
        {'name': 'jarvis_route', 'type': 'choice', 'choice': route, 'confidence': .96},
        {'name': 'explicit_sleep_intent', 'type': 'predicate', 'probability': sleep},
        {'name': 'private_memory_required', 'type': 'predicate', 'probability': memory},
    ], 'usage': {'input_tokens': 412}}


class Repair12Tests(unittest.IsolatedAsyncioTestCase):
    def test_matched_mode_uses_real_core_luna_in_both_arms(self):
        self.assertIn('"mini-overlap-luna-decisions-shadow"', LAUNCHER)
        self.assertIn('luna_probe = sys.argv[1] == "mini-overlap-luna"', LAUNCHER)
        self.assertIn('luna_probe = luna_probe or sys.argv[1] == "mini-overlap-luna-decisions-shadow"', LAUNCHER)
        self.assertIn('decisions_shadow = sys.argv[1] in {"mini-overlap-decisions-shadow", "mini-overlap-luna-decisions-shadow"}', LAUNCHER)
        self.assertIn('"JARVIS_CORE_LUNA_PROBE"] = "1" if luna_probe else "0"', LAUNCHER)
        self.assertIn('"JARVIS_REALTIME_OVERLAP_PROBE"] = "1" if overlap_probe else "0"', LAUNCHER)
        self.assertIn('"JARVIS_PARALLEL_SHADOW_PROBE"] = "0"', LAUNCHER)

    def test_actual_launch_environment_has_one_intended_difference(self):
        captured = []
        def fake_call(command, *, cwd, env, shell):
            captured.append({k: v for k, v in env.items() if k.startswith('JARVIS_')})
            return 0
        for mode in ('mini-overlap-luna', 'mini-overlap-luna-decisions-shadow'):
            with mock.patch('sys.argv', ['realtime_ab.py', mode]), \
                 mock.patch.object(realtime_ab.subprocess, 'call', side_effect=fake_call):
                self.assertEqual(realtime_ab.main(), 0)
        before, shadow = captured
        self.assertEqual(before['JARVIS_CORE_LUNA_PROBE'], '1')
        self.assertEqual(shadow['JARVIS_CORE_LUNA_PROBE'], '1')
        self.assertEqual(before['JARVIS_REALTIME_OVERLAP_PROBE'], '1')
        self.assertEqual(shadow['JARVIS_REALTIME_OVERLAP_PROBE'], '1')
        self.assertEqual(before['JARVIS_DECISIONS_SHADOW_PROBE'], '0')
        self.assertEqual(shadow['JARVIS_DECISIONS_SHADOW_PROBE'], '1')
        self.assertEqual({k: v for k, v in before.items() if k != 'JARVIS_DECISIONS_SHADOW_PROBE'},
                         {k: v for k, v in shadow.items() if k != 'JARVIS_DECISIONS_SHADOW_PROBE'})

    def test_no_decisions_to_authority_path(self):
        self.assertIn('if self.config.core_luna_probe:', HOST)
        self.assertIn('if self.config.decisions_shadow_probe:', HOST)
        self.assertIn('self._decisions_shadow.observe_transcript(', HOST)
        self.assertIn('self._decisions_shadow.observe_voice_timing(', HOST)
        self.assertNotIn('self._decisions_shadow.authorize', HOST)
        self.assertNotIn('self._decisions_shadow.route_', HOST)
        self.assertNotIn('self._decisions_shadow.execute', HOST)
        self.assertIn("overlapDecisionRef.current === 'direct' && overlapDirectVerifiedRef.current", RENDERER)
        self.assertIn("phase:'sleep_evidence_check'", RENDERER)

    async def test_matched_observation_reports_measured_and_counterfactual_separately(self):
        async def handler(req):
            self.assertEqual(req.url.path, '/v1/decisions')
            return httpx.Response(200, json=result())
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            logs = []
            probe = DecisionsShadowProbe('dev-test', client=client, log=logs.append)
            probe.observe_transcript(2, 'What is the capital of France?', transcript_ms=400)
            probe.observe_mini_route(2, 'direct')
            probe.observe_voice_timing(2, speech_end_to_route_ms=900, speech_end_to_first_audio_ms=1500)
            await asyncio.gather(*probe._tasks)
            rows = [line for line in logs if line.startswith('[Jarvis Repair12 A/B]')]
            self.assertEqual(len(rows), 1)
            self.assertIn('mini_route_ms=900', rows[0])
            self.assertIn('first_audio_ms=1500', rows[0])
            self.assertIn('decisions_status=ok', rows[0])
            self.assertIn('authority=mini', rows[0])
            self.assertIn('actual_decisions_audio_gain=not_measured', rows[0])
            self.assertTrue(any('phase=compare' in x and 'agreement=yes' in x for x in logs))
            self.assertFalse(any('What is the capital' in x for x in logs))
            probe.observe_voice_timing(2, speech_end_to_route_ms=901, speech_end_to_first_audio_ms=1501)
            self.assertEqual(len([x for x in logs if x.startswith('[Jarvis Repair12 A/B]')]), 1)
            await probe.close()

    async def test_unsafe_direct_disagreement_does_not_change_lifecycle(self):
        async def handler(req):
            return httpx.Response(200, json=result('direct', sleep=.98, memory=.01))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            logs = []
            probe = DecisionsShadowProbe('dev-test', client=client, log=logs.append)
            probe.observe_mini_route(5, 'sleep')
            probe.observe_transcript(5, "Thanks Jarvis, that's all", transcript_ms=380)
            probe.observe_voice_timing(5, speech_end_to_route_ms=820)
            await asyncio.gather(*probe._tasks)
            self.assertTrue(any('agreement=no | authority=mini' in x for x in logs))
            # Never make a direct authorization or speech-timing claim on sleep-only turns.
            self.assertFalse(any(x.startswith('[Jarvis Repair12 A/B]') for x in logs))
            await probe.close()

    async def test_api_failure_is_not_confused_with_fast_authorization(self):
        async def handler(req):
            return httpx.Response(503)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            logs = []
            probe = DecisionsShadowProbe('dev-test', client=client, log=logs.append)
            probe.observe_transcript(4, 'Hello', transcript_ms=300)
            probe.observe_mini_route(4, 'direct')
            probe.observe_voice_timing(4, speech_end_to_route_ms=750, speech_end_to_first_audio_ms=1300)
            await asyncio.gather(*probe._tasks)
            report = next(x for x in logs if x.startswith('[Jarvis Repair12 A/B]'))
            self.assertIn('decisions_status=http_503', report)
            self.assertIn('decisions_ready_ms=n/a', report)
            self.assertIn('potential_route_headroom_ms=n/a', report)
            await probe.close()

    def test_summary_excludes_wake_and_does_not_invent_decisions_gain(self):
        data = '''[Jarvis Overlap] turn=1 | phase=direct | decision_ms=900
[Desktop latency] turn=1 | route=overlap_stream_probe | speech_end->route=900 ms | speech_end->first_audio=2000 ms
[Jarvis Overlap] turn=2 | phase=direct | decision_ms=700
[Desktop latency] turn=2 | route=overlap_stream_probe | speech_end->route=700 ms | speech_end->first_audio=1300 ms
[Jarvis Repair12 A/B] turn=2 | mini_route=direct | decisions_route=direct | decisions_status=ok | agreement=yes | transcript_ms=410 | decisions_api_ms=205 | decisions_ready_ms=615 | mini_route_ms=700 | potential_route_headroom_ms=85 | first_audio_ms=1300 | unsafe_direct=false | authority=mini | actual_decisions_audio_gain=not_measured
[Jarvis Overlap] turn=3 | phase=tool | decision_ms=950
[Desktop latency] turn=3 | route=overlap_stream_probe | speech_end->route=950 ms | speech_end->first_audio=2190 ms
'''
        turns = parse_log(data)
        summary = compute_summary(turns, exclude_first=True)
        self.assertEqual(summary['direct_count'], 1)
        self.assertEqual(summary['median_first_audio_ms'], 1300)
        self.assertEqual(summary['median_mini_route_ms'], 700)
        self.assertEqual(summary['median_potential_headroom_ms'], 85)
        self.assertEqual(summary['decisions_disagreements'], 0)
        self.assertNotIn('measured_decisions_audio_gain_ms', summary)


if __name__ == '__main__':
    unittest.main()
