"""Cost accounting and comparison boundary tests, without network/API calls."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from providers.voice_frontend.openai_realtime.bench import (
    PRICES, RealtimeBenchmark, estimate_realtime_cost,
)
from providers.voice_frontend.openai_realtime.config import OpenAIRealtimeConfig
from providers.voice_frontend.openai_realtime.webrtc import build_realtime_session

ROOT = Path(__file__).resolve().parents[2]


class BillingTests(unittest.TestCase):
    def setUp(self):
        self.usage = {
            'input_tokens': 150, 'output_tokens': 70,
            'input_token_details': {'text_tokens': 100, 'audio_tokens': 50, 'cached_tokens': 30,
                                    'cached_tokens_details': {'text_tokens': 20, 'audio_tokens': 10, 'image_tokens': 0}},
            'output_token_details': {'text_tokens': 30, 'audio_tokens': 40},
        }

    def test_known_models_have_pricing(self):
        self.assertIn('gpt-realtime-2.1', PRICES)
        self.assertIn('gpt-realtime-2.1-mini', PRICES)

    def test_cached_input_billed_once(self):
        expected = (80 * .6 + 20 * .06 + 40 * 10 + 10 * .3 + 30 * 2.4 + 40 * 20) / 1_000_000
        estimate = estimate_realtime_cost('gpt-realtime-2.1-mini', self.usage)
        self.assertAlmostEqual(estimate.cost_usd, expected)
        self.assertEqual(estimate.cached_in, 30)

    def test_full_realtime_is_higher_cost(self):
        mini = estimate_realtime_cost('gpt-realtime-2.1-mini', self.usage)
        full = estimate_realtime_cost('gpt-realtime-2.1', self.usage)
        self.assertGreater(full.cost_usd, mini.cost_usd)

    def test_missing_usage_has_no_fake_zero(self):
        self.assertIsNone(estimate_realtime_cost('gpt-realtime-2.1-mini', {}).cost_usd)
        self.assertIsNone(estimate_realtime_cost('gpt-realtime-2.1-mini', {'input_tokens': 5, 'output_tokens': 0}).cost_usd)
        self.assertIsNone(estimate_realtime_cost('unverified', self.usage).cost_usd)

    def test_missing_cached_modality_breakdown_has_no_fake_estimate(self):
        sample = {**self.usage, 'input_token_details': {
            **self.usage['input_token_details'], 'cached_tokens_details': None}}
        self.assertEqual(estimate_realtime_cost('gpt-realtime-2.1', sample).note,
                         'cached_breakdown_missing')

    def test_unclassified_input_never_undercharged(self):
        sample = {**self.usage, 'input_tokens': 160}
        self.assertEqual(estimate_realtime_cost('gpt-realtime-2.1', sample).note, 'unclassified_tokens')

    def test_turn_aggregation_and_no_duplicate_response(self):
        meter = RealtimeBenchmark('gpt-realtime-2.1-mini')
        meter.on_user(2, 'What is the Red Planet?')
        meter.on_route(2, 'direct')
        meter.on_latency(2, 900)
        response = {'id': 'r-1', 'status': 'completed', 'usage': self.usage, 'output': []}
        self.assertIsNotNone(meter.on_response(response, turn=2, stage='answer'))
        self.assertIsNone(meter.on_response(response, turn=2, stage='answer'))
        summary = meter.on_reply(2, 'Mars.')
        self.assertIn('reply_words=1', summary)
        self.assertIn('user_words=5', summary)
        self.assertIn('first_audio_ms=900', summary)
        self.assertIn('core_cost=excluded', summary)
        self.assertEqual(meter.turn(2).priced_responses, 1)
        self.assertIn('turns=1', meter.summary())

    def test_tool_trace_does_not_execute_tools(self):
        meter = RealtimeBenchmark('gpt-realtime-2.1')
        meter.on_route(1, 'reasoning')
        meter.on_core(1, 'core:reasoning')
        line = meter.on_response({'id': 'rt', 'status': 'completed', 'usage': self.usage,
                                  'output': [{'type': 'function_call', 'name': 'route_jarvis_turn'}]},
                                 turn=1, stage='route')
        self.assertIn('function_calls=route_jarvis_turn', line)
        self.assertEqual(meter.turn(1).core_calls, 1)

    def test_env_model_override_and_session_selection(self):
        for model in ('gpt-realtime-2.1-mini', 'gpt-realtime-2.1'):
            config = OpenAIRealtimeConfig.from_env(env={'OPENAI_API_KEY': 'fake', 'JARVIS_REALTIME_MODEL': model})
            self.assertEqual(build_realtime_session(config)['model'], model)

    def test_launcher_disables_shadow_for_clean_comparison(self):
        contents = (ROOT / 'scripts/realtime_ab.py').read_text(encoding='utf-8')
        self.assertIn('JARVIS_PARALLEL_SHADOW_PROBE', contents)
        self.assertIn('gpt-realtime-2.1-mini', contents)
        self.assertIn('gpt-realtime-2.1', contents)
        self.assertNotIn('OPENAI_API_KEY =', contents)

    def test_existing_ownership_gate_preserved(self):
        contents = (ROOT / 'apps/desktop_alpha.py').read_text(encoding='utf-8')
        self.assertIn('"tool_choice": {"type": "function", "name": ROUTE_TURN_TOOL_NAME}', contents)
        self.assertIn('output_modalities": ["text"]', contents)
        self.assertIn('"kind": "response_policy"', contents)
        self.assertIn('"realtime_event"', contents)

if __name__ == '__main__':
    unittest.main()
