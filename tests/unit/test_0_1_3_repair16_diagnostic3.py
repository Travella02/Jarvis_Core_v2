"""Repair16 Diagnostic3: preserve safe WebSocket terminal response metadata."""
from __future__ import annotations

import asyncio
import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace

from apps.desktop_luna import DesktopLunaDelegator, _safe_core_budget_fields
from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.intelligence import (
    DelegationStatus, IntelligenceContext, IntelligenceEventType, ReasoningPolicy,
)
from providers.intelligence.openai.config import OpenAIProviderConfig
from providers.intelligence.openai.provider import OpenAIProvider


class FakeWebSocket:
    def __init__(self, events):
        self.events = list(events)
        self.params = None
        self.response = self
        self.closed = False

    async def create(self, **kwargs):
        self.params = kwargs

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.events:
            raise StopAsyncIteration
        return self.events.pop(0)

    async def close(self):
        self.closed = True


class Router:
    def __init__(self, provider):
        self.provider = provider

    def resolve(self, route):
        if route != 'primary':
            raise KeyError(route)
        return self.provider


class Orchestrator:
    def __init__(self, provider, result):
        self.provider_router = Router(provider)
        self.result = result

    async def execute(self, request, *, conversation):
        return self.result


class Conversation:
    async def cancel_active_turn(self, reason):
        return True


def event(name, **kwargs):
    return SimpleNamespace(type=name, **kwargs)


def response(identifier, **kwargs):
    return SimpleNamespace(id=identifier, **kwargs)


class Diagnostic3Tests(unittest.IsolatedAsyncioTestCase):
    async def run_ws(self, *, complete=False, terminal_usage=True, reason='max_output_tokens'):
        secret = 'sk-NEVER_LOG_THIS_or_the_raw_user_question'
        final = response(
            'resp-ws-347',
            status='completed' if complete else 'incomplete',
            incomplete_details=None if complete else {'reason': reason},
            usage=({'input_tokens': 1234, 'output_tokens': 256,
                    'output_tokens_details': {'reasoning_tokens': 211}}
                   if terminal_usage else None),
            output=[{'text': secret}],
            error=secret,
        )
        ws = FakeWebSocket([
            event('response.created', response=response('resp-ws-347')),
            event('response.output_text.delta', delta=secret),
            event('response.completed' if complete else 'response.incomplete', response=final),
        ])
        cfg = OpenAIProviderConfig(
            api_key='not-a-real-key', model='gpt-6-luna',
            voice_max_output_tokens=256, voice_transport='websocket',
        )
        provider = OpenAIProvider(cfg, client=SimpleNamespace())
        provider._voice_connection = ws  # deterministic fake transport: no network
        context = IntelligenceContext(
            trace=CorrelationContext('conversation-d3', 'request-d3', 'trace-d3'),
            messages=({'role': 'user', 'content': 'Analyze 3 architectures'},),
            metadata={'input_channel': 'voice', 'conversation_id': 'conversation-d3'},
        )
        events = [x async for x in provider.stream_response(
            context, (), ReasoningPolicy(level='low'), CancellationToken())]
        return provider, ws, events, secret

    async def test_websocket_incomplete_metadata_survives_before_terminal_yield(self):
        provider, ws, events, secret = await self.run_ws()
        self.assertEqual(events[-1].event_type, IntelligenceEventType.DEGRADED)
        self.assertEqual(ws.params['max_output_tokens'], 256)
        telemetry = provider.response_diagnostics('resp-ws-347')
        self.assertEqual(telemetry['transport'], 'websocket')
        self.assertEqual(telemetry['requested_model'], 'gpt-6-luna')
        self.assertEqual(telemetry['requested_output_limit'], 256)
        self.assertEqual(telemetry['response_status'], 'incomplete')
        self.assertEqual(telemetry['incomplete_reason'], 'max_output_tokens')
        self.assertEqual(telemetry['input_tokens'], 1234)
        self.assertEqual(telemetry['output_tokens'], 256)
        self.assertEqual(telemetry['reasoning_tokens'], 211)
        self.assertNotIn(secret, repr(telemetry))
        self.assertEqual(provider.response_diagnostics('resp-other'), {})
        self.assertEqual(provider.response_diagnostics(None), {})

    async def test_websocket_completed_metadata_and_missing_usage(self):
        provider, ws, events, secret = await self.run_ws(complete=True, terminal_usage=False)
        self.assertEqual(events[-1].event_type, IntelligenceEventType.COMPLETED)
        telemetry = provider.response_diagnostics('resp-ws-347')
        self.assertEqual(telemetry['response_status'], 'completed')
        self.assertEqual(telemetry['requested_output_limit'], 256)
        self.assertNotIn('output_tokens', telemetry)
        self.assertNotIn(secret, repr(telemetry))

    async def test_websocket_unknown_incomplete_reason_is_not_logged_raw(self):
        reason = 'raw_fake_secret_sk-NEVER_LOG_THIS_or_the_raw_user_question'
        provider, ws, events, secret = await self.run_ws(reason=reason)
        telemetry = provider.response_diagnostics('resp-ws-347')
        self.assertEqual(telemetry['incomplete_reason'], 'unknown')
        self.assertNotIn(reason, repr(telemetry))

    async def test_core_logs_sanitized_websocket_telemetry_and_unchanged_failure_message(self):
        provider, ws, events, secret = await self.run_ws()
        result = SimpleNamespace(
            status=DelegationStatus.FAILED, detail='OpenAI response ended incomplete',
            text=secret,
            decision=SimpleNamespace(route_name='primary'),
            provider_response_id='resp-ws-347',
        )
        orchestrator = Orchestrator(provider, result)
        fields = _safe_core_budget_fields(orchestrator, result)
        self.assertEqual(fields['diagnostic_match'], 'true')
        self.assertEqual(fields['model'], 'gpt-6-luna')
        self.assertEqual(fields['output_limit'], '256')
        self.assertEqual(fields['reason'], 'max_output_tokens')
        self.assertEqual(fields['reasoning_tokens'], '211')
        sent = []

        async def notify(message):
            sent.append(message)

        bridge = DesktopLunaDelegator(
            orchestrator=orchestrator, conversation=Conversation(), notify=notify,
        )
        output = io.StringIO()
        with redirect_stdout(output):
            bridge.transcript(1, 'Please analyze architectures')
            self.assertTrue(bridge.selected(1))
            for _ in range(300):
                if not bridge._tasks:
                    break
                await asyncio.sleep(.001)
            else:
                self.fail('Bridge did not finish')
            await bridge.close()
        text = output.getvalue()
        self.assertIn('incomplete_reason=max_output_tokens', text)
        self.assertIn('output_limit=256', text)
        self.assertIn('reasoning_tokens=211', text)
        self.assertNotIn(secret, text)
        self.assertEqual(sent[0]['text'], "I couldn't complete that request with Luna. Please try again.")
        self.assertEqual(sent[0]['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
