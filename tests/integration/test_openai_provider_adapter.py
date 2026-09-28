import asyncio
import unittest
from types import SimpleNamespace

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.intelligence import (
    IntelligenceContext,
    IntelligenceEventType,
    ProviderHealthState,
    ReasoningPolicy,
)
from core.tools import ToolDefinition
from providers.intelligence.openai import OpenAIProvider, OpenAIProviderConfig


class FakeStream:
    def __init__(self, events):
        self.events = list(events)
        self.index = 0
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.closed or self.index >= len(self.events):
            raise StopAsyncIteration
        item = self.events[self.index]
        self.index += 1
        await asyncio.sleep(0)
        return item

    async def close(self):
        self.closed = True


class FakeResponses:
    def __init__(self, stream):
        self.stream = stream
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.stream


class FakeClient:
    def __init__(self, events):
        self.stream = FakeStream(events)
        self.responses = FakeResponses(self.stream)




class FakeWSResponseResource:
    def __init__(self, connection):
        self.connection = connection

    async def create(self, **kwargs):
        self.connection.calls.append(kwargs)
        self.connection.batch_index += 1
        self.connection.event_index = 0


class FakeWSConnection:
    def __init__(self, batches):
        self.batches = [list(batch) for batch in batches]
        self.batch_index = -1
        self.event_index = 0
        self.calls = []
        self.closed = False
        self.response = FakeWSResponseResource(self)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.closed or self.batch_index < 0 or self.batch_index >= len(self.batches):
            raise StopAsyncIteration
        batch = self.batches[self.batch_index]
        if self.event_index >= len(batch):
            raise StopAsyncIteration
        item = batch[self.event_index]
        self.event_index += 1
        await asyncio.sleep(0)
        return item

    async def close(self):
        self.closed = True


class FakeWSManager:
    def __init__(self, connection):
        self.connection = connection

    async def enter(self):
        return self.connection


class FakeWebSocketResponses(FakeResponses):
    def __init__(self, http_stream, ws_connection):
        super().__init__(http_stream)
        self.ws_connection = ws_connection
        self.connect_calls = 0

    def connect(self, **kwargs):
        self.connect_calls += 1
        return FakeWSManager(self.ws_connection)


class FakeWebSocketClient:
    def __init__(self, batches):
        self.stream = FakeStream([])
        self.ws_connection = FakeWSConnection(batches)
        self.responses = FakeWebSocketResponses(self.stream, self.ws_connection)


def event(event_type, **kwargs):
    return SimpleNamespace(type=event_type, **kwargs)


def response(response_id="resp_test", **kwargs):
    return SimpleNamespace(id=response_id, **kwargs)


class OpenAIProviderAdapterTests(unittest.IsolatedAsyncioTestCase):
    def context(self, request_id="req-1", *, metadata=None, messages=None):
        return IntelligenceContext(
            trace=CorrelationContext("corr-1", request_id, "turn-1"),
            messages=messages or ({"role": "user", "content": "hello"},),
            metadata=metadata or {},
        )

    async def collect(self, provider, *, tools=(), token=None, policy=None, request_id="req-1"):
        return [
            item
            async for item in provider.stream_response(
                self.context(request_id),
                tools,
                policy or ReasoningPolicy(level="standard"),
                token or CancellationToken(),
            )
        ]

    async def test_metadata_capabilities_and_luna_limits(self) -> None:
        provider = OpenAIProvider(OpenAIProviderConfig(api_key="test"), client=FakeClient([]))
        self.assertEqual(provider.metadata.provider, "openai")
        self.assertEqual(provider.metadata.model, "gpt-6-luna")
        self.assertTrue(provider.supports_tools())
        self.assertTrue(provider.supports_vision())
        self.assertTrue(provider.supports_reasoning_levels())
        self.assertEqual(provider.context_limits().max_input_tokens, 1_050_000)
        self.assertEqual(provider.context_limits().max_output_tokens, 128_000)

    async def test_streams_text_and_completion_without_sdk_objects_leaking(self) -> None:
        usage = SimpleNamespace(model_dump=lambda: {"input_tokens": 12, "output_tokens": 3})
        client = FakeClient(
            [
                event("response.created", response=response("resp_123")),
                event("response.output_text.delta", delta="Luna "),
                event("response.output_text.delta", delta="online"),
                event(
                    "response.completed",
                    response=response("resp_123", model="gpt-5.6-luna", status="completed", usage=usage),
                ),
            ]
        )
        provider = OpenAIProvider(OpenAIProviderConfig(api_key="test"), client=client)
        events = await self.collect(provider)
        self.assertEqual(
            [item.event_type for item in events],
            [
                IntelligenceEventType.TEXT_DELTA,
                IntelligenceEventType.TEXT_DELTA,
                IntelligenceEventType.COMPLETED,
            ],
        )
        self.assertEqual("".join(item.text_delta or "" for item in events), "Luna online")
        self.assertEqual(events[-1].provider_response_id, "resp_123")
        self.assertEqual(events[-1].metadata["usage"]["input_tokens"], 12)
        call = client.responses.calls[0]
        self.assertEqual(call["model"], "gpt-6-luna")
        self.assertTrue(call["stream"])
        self.assertFalse(call["store"])
        self.assertEqual(call["reasoning"], {"effort": "medium"})
        self.assertEqual(call["max_output_tokens"], 4096)

    async def test_voice_context_requests_low_text_verbosity(self) -> None:
        client = FakeClient([event("response.completed", response=response("resp_voice", usage=None))])
        provider = OpenAIProvider(OpenAIProviderConfig(api_key="test"), client=client)
        context = self.context("req-voice", metadata={"input_channel": "voice"})
        events = [
            item
            async for item in provider.stream_response(
                context, (), ReasoningPolicy(level="none"), CancellationToken()
            )
        ]
        self.assertEqual(events[-1].event_type, IntelligenceEventType.COMPLETED)
        self.assertEqual(client.responses.calls[0]["reasoning"], {"effort": "none"})
        call = client.responses.calls[0]
        self.assertEqual(call["text"], {"verbosity": "low"})
        self.assertEqual(call["max_output_tokens"], 256)
        self.assertEqual(call["prompt_cache_options"], {"mode": "implicit", "ttl": "30m"})

    async def test_optional_fast_service_tier_is_provider_owned(self) -> None:
        client = FakeClient([event("response.completed", response=response("resp_fast", usage=None))])
        provider = OpenAIProvider(
            OpenAIProviderConfig(api_key="test", service_tier="fast"),
            client=client,
        )
        context = self.context("req-fast", metadata={"input_channel": "voice"})
        events = [
            item
            async for item in provider.stream_response(
                context, (), ReasoningPolicy(level="none"), CancellationToken()
            )
        ]
        self.assertEqual(events[-1].event_type, IntelligenceEventType.COMPLETED)
        self.assertEqual(client.responses.calls[0]["service_tier"], "fast")

    async def test_tool_call_becomes_non_executable_tool_request(self) -> None:
        tool_item = SimpleNamespace(
            type="function_call",
            name="browser_open_new_tab",
            arguments="{}",
            call_id="call_123",
        )
        client = FakeClient(
            [
                event("response.created", response=response("resp_tools")),
                event("response.output_item.done", item=tool_item),
                event(
                    "response.completed",
                    response=response("resp_tools", model="gpt-5.6-luna", status="completed", usage=None),
                ),
            ]
        )
        provider = OpenAIProvider(OpenAIProviderConfig(api_key="test"), client=client)
        tool = ToolDefinition(
            "browser_open_new_tab",
            "Request a new tab",
            {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        )
        events = await self.collect(provider, tools=(tool,), policy=ReasoningPolicy(level="quick"))
        requests = [item.tool_request for item in events if item.tool_request]
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(request.tool_name, "browser_open_new_tab")
        self.assertEqual(request.operation, "invoke")
        self.assertEqual(dict(request.arguments), {})
        self.assertEqual(request.provider_call_id, "call_123")
        self.assertFalse(any(callable(value) for value in request.arguments.values()))
        api_tool = client.responses.calls[0]["tools"][0]
        self.assertEqual(api_tool["type"], "function")
        self.assertEqual(api_tool["name"], "browser_open_new_tab")
        self.assertEqual(client.responses.calls[0]["reasoning"], {"effort": "low"})

    async def test_invalid_provider_tool_json_fails_closed(self) -> None:
        tool_item = SimpleNamespace(
            type="function_call",
            name="unsafe",
            arguments="not-json",
            call_id="call_bad",
        )
        provider = OpenAIProvider(
            OpenAIProviderConfig(api_key="test"),
            client=FakeClient([event("response.output_item.done", item=tool_item)]),
        )
        events = await self.collect(provider)
        self.assertEqual(events[-1].event_type, IntelligenceEventType.ERROR)
        self.assertIn("ValueError", events[-1].detail)
        self.assertFalse(any(item.tool_request for item in events))

    async def test_pre_cancelled_request_never_creates_provider_stream(self) -> None:
        client = FakeClient([event("response.output_text.delta", delta="should-not-run")])
        provider = OpenAIProvider(OpenAIProviderConfig(api_key="test"), client=client)
        token = CancellationToken()
        token.cancel("cancelled before start")
        events = await self.collect(provider, token=token, request_id="req-pre-cancel")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, IntelligenceEventType.CANCELLED)
        self.assertEqual(client.responses.calls, [])

    async def test_nested_response_failure_code_is_sanitized(self) -> None:
        nested_error = SimpleNamespace(code="rate_limit_exceeded", message="secret provider detail")
        failed_response = response("resp_fail", error=nested_error)
        provider = OpenAIProvider(
            OpenAIProviderConfig(api_key="test"),
            client=FakeClient([event("response.failed", response=failed_response)]),
        )
        events = await self.collect(provider, request_id="req-fail")
        self.assertEqual(events[-1].event_type, IntelligenceEventType.ERROR)
        self.assertEqual(events[-1].detail, "OpenAI response error (rate_limit_exceeded)")
        self.assertNotIn("secret provider detail", events[-1].detail)

    async def test_cancel_closes_active_stream_and_emits_cancelled(self) -> None:
        client = FakeClient(
            [
                event("response.output_text.delta", delta="first"),
                event("response.output_text.delta", delta="second"),
            ]
        )
        provider = OpenAIProvider(OpenAIProviderConfig(api_key="test"), client=client)
        generator = provider.stream_response(
            self.context("req-cancel"),
            (),
            ReasoningPolicy(level="quick"),
            CancellationToken(),
        )
        first = await anext(generator)
        self.assertEqual(first.text_delta, "first")
        await provider.cancel("req-cancel")
        second = await anext(generator)
        self.assertEqual(second.event_type, IntelligenceEventType.CANCELLED)
        self.assertTrue(client.stream.closed)
        with self.assertRaises(StopAsyncIteration):
            await anext(generator)

    async def test_voice_websocket_reuses_connection_and_continues_only_exact_core_chain(self) -> None:
        client = FakeWebSocketClient(
            [
                [
                    event("response.created", response=response("resp_ws_1")),
                    event("response.output_text.delta", delta="Hello there."),
                    event("response.completed", response=response("resp_ws_1", usage=None)),
                ],
                [
                    event("response.created", response=response("resp_ws_2")),
                    event("response.output_text.delta", delta="Second answer."),
                    event("response.completed", response=response("resp_ws_2", usage=None)),
                ],
            ]
        )
        provider = OpenAIProvider(
            OpenAIProviderConfig(api_key="test", voice_transport="websocket"),
            client=client,
        )
        metadata = {"input_channel": "voice", "conversation_id": "conversation-test"}
        first_context = self.context(
            "req-ws-1",
            metadata=metadata,
            messages=(
                {"role": "developer", "content": "Speak briefly."},
                {"role": "user", "content": "Hello"},
            ),
        )
        first = [
            item
            async for item in provider.stream_response(
                first_context, (), ReasoningPolicy(level="none"), CancellationToken()
            )
        ]
        self.assertEqual(first[-1].event_type, IntelligenceEventType.COMPLETED)

        second_context = self.context(
            "req-ws-2",
            metadata=metadata,
            messages=(
                {"role": "developer", "content": "Speak briefly."},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hello there."},
                {"role": "user", "content": "Continue"},
            ),
        )
        second = [
            item
            async for item in provider.stream_response(
                second_context, (), ReasoningPolicy(level="none"), CancellationToken()
            )
        ]
        self.assertEqual(second[-1].event_type, IntelligenceEventType.COMPLETED)
        self.assertEqual(client.responses.connect_calls, 1)
        first_call, second_call = client.ws_connection.calls
        self.assertNotIn("previous_response_id", first_call)
        self.assertEqual(len(first_call["input"]), 2)
        self.assertEqual(second_call["previous_response_id"], "resp_ws_1")
        self.assertEqual(second_call["input"], [{"role": "user", "content": "Continue"}])
        self.assertEqual(first_call["stream_id"], second_call["stream_id"])
        self.assertNotIn("stream", first_call)
        await provider.close()

    async def test_voice_websocket_resets_to_full_context_when_core_snapshot_diverges(self) -> None:
        client = FakeWebSocketClient(
            [
                [
                    event("response.created", response=response("resp_a")),
                    event("response.output_text.delta", delta="Answer A"),
                    event("response.completed", response=response("resp_a", usage=None)),
                ],
                [
                    event("response.created", response=response("resp_b")),
                    event("response.output_text.delta", delta="Answer B"),
                    event("response.completed", response=response("resp_b", usage=None)),
                ],
            ]
        )
        provider = OpenAIProvider(
            OpenAIProviderConfig(api_key="test", voice_transport="websocket"), client=client
        )
        metadata = {"input_channel": "voice", "conversation_id": "conversation-reset"}
        for request_id, messages in (
            ("req-a", ({"role": "user", "content": "A"},)),
            ("req-b", ({"role": "system", "content": "Context changed"}, {"role": "user", "content": "B"})),
        ):
            context = self.context(request_id, metadata=metadata, messages=messages)
            _ = [
                item
                async for item in provider.stream_response(
                    context, (), ReasoningPolicy(level="none"), CancellationToken()
                )
            ]
        second_call = client.ws_connection.calls[1]
        self.assertNotIn("previous_response_id", second_call)
        self.assertEqual(len(second_call["input"]), 2)
        await provider.close()

    async def test_health_distinguishes_configuration_and_success(self) -> None:
        missing = OpenAIProvider(OpenAIProviderConfig(api_key=None))
        self.assertEqual((await missing.health()).state, ProviderHealthState.NOT_CONFIGURED)

        client = FakeClient(
            [
                event(
                    "response.completed",
                    response=response("resp_ok", model="gpt-5.6-luna", status="completed", usage=None),
                )
            ]
        )
        provider = OpenAIProvider(OpenAIProviderConfig(api_key="test"), client=client)
        self.assertEqual((await provider.health()).state, ProviderHealthState.CONFIGURED)
        await self.collect(provider)
        self.assertEqual((await provider.health()).state, ProviderHealthState.HEALTHY)


if __name__ == "__main__":
    unittest.main()
