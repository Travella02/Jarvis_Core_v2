from __future__ import annotations

import asyncio
import unittest
from collections.abc import AsyncIterator, Sequence

import httpx

from apps.runtime_api import create_app
from core.common.cancellation import CancellationToken
from core.intelligence import (
    ContextLimits,
    IntelligenceContext,
    IntelligenceEvent,
    IntelligenceEventType,
    IntelligenceProvider,
    ProviderHealth,
    ProviderHealthState,
    ProviderMetadata,
    ReasoningPolicy,
)
from core.runtime import (
    ClientCommandError,
    ClientCommandStatus,
    IntelligenceProviderRouter,
    JarvisRuntime,
    RuntimeSettings,
)
from core.tools import ToolDefinition


class _CommandProvider(IntelligenceProvider):
    def __init__(self, *, hold: bool = False) -> None:
        self.hold = hold
        self.calls = 0
        self.cancelled_request_ids: list[str] = []
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(provider="diagnostic", model="client-command-test")

    async def stream_response(
        self,
        context: IntelligenceContext,
        tools: Sequence[ToolDefinition],
        reasoning_policy: ReasoningPolicy,
        cancellation_token: CancellationToken,
    ) -> AsyncIterator[IntelligenceEvent]:
        self.calls += 1
        self.started.set()
        while self.hold and not self.release.is_set() and not cancellation_token.is_cancelled:
            await asyncio.sleep(0.005)
        if cancellation_token.is_cancelled:
            yield IntelligenceEvent(
                event_type=IntelligenceEventType.CANCELLED,
                detail=cancellation_token.reason,
            )
            return
        yield IntelligenceEvent(
            event_type=IntelligenceEventType.TEXT_DELTA,
            text_delta="Runtime client command completed through Conversation Core.",
        )
        yield IntelligenceEvent(
            event_type=IntelligenceEventType.COMPLETED,
            provider_response_id="client-command-test-response",
        )

    def supports_tools(self) -> bool:
        return False

    def supports_vision(self) -> bool:
        return False

    def supports_reasoning_levels(self) -> bool:
        return False

    def context_limits(self) -> ContextLimits:
        return ContextLimits(max_input_tokens=4096, max_output_tokens=256)

    async def cancel(self, request_id: str) -> None:
        self.cancelled_request_ids.append(request_id)

    async def health(self) -> ProviderHealth:
        return ProviderHealth(ProviderHealthState.HEALTHY, "client command test ready")


class RuntimeClientCommandTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.provider = _CommandProvider()
        router = IntelligenceProviderRouter(default_route="primary")
        router.register("primary", self.provider, make_default=True)
        self.runtime = JarvisRuntime(
            settings=RuntimeSettings(event_history_limit=128),
            provider_router=router,
            version="0.0.8-test",
        )
        self.runtime.start()
        self.core = self.runtime.create_conversation(
            user_id="client-command-user",
            speaker_id="client-command-speaker",
            device_id="client-command-device",
        )

    async def asyncTearDown(self) -> None:
        self.provider.release.set()
        await asyncio.sleep(0)
        self.runtime.close()

    def _submit_args(self, *, request_id: str = "client-request-001", text: str = "hello") -> dict[str, str]:
        return {
            "runtime_id": self.runtime.runtime_id,
            "conversation_id": self.core.context.conversation_id,
            "client_request_id": request_id,
            "client_id": "desktop-test-client",
            "text": text,
        }

    async def test_typed_client_request_uses_same_core_and_server_owned_trace(self) -> None:
        core_identity = id(self.runtime.conversation)
        receipt = await self.runtime.client_commands.submit_typed(**self._submit_args())
        record = await self.runtime.client_commands.wait(receipt.record.command_id)

        self.assertEqual(id(self.runtime.conversation), core_identity)
        self.assertEqual(record.status, ClientCommandStatus.COMPLETED)
        self.assertTrue(record.trace.correlation_id.startswith("corr-"))
        self.assertTrue(record.trace.request_id.startswith("req-"))
        self.assertTrue(record.trace.turn_id.startswith("turn-"))
        self.assertEqual(self.provider.calls, 1)
        event_types = [event.event_type for event in self.runtime.event_bus.history]
        self.assertIn("runtime.client.command.accepted", event_types)
        self.assertIn("user.text.received", event_types)
        self.assertIn("response.completed", event_types)
        self.assertIn("runtime.client.command.completed", event_types)

    async def test_duplicate_retry_returns_same_command_without_second_execution(self) -> None:
        first = await self.runtime.client_commands.submit_typed(**self._submit_args())
        await self.runtime.client_commands.wait(first.record.command_id)
        second = await self.runtime.client_commands.submit_typed(**self._submit_args())

        self.assertTrue(second.duplicate)
        self.assertEqual(second.record.command_id, first.record.command_id)
        self.assertEqual(second.record.trace, first.record.trace)
        self.assertEqual(self.provider.calls, 1)

    async def test_idempotency_key_cannot_be_rebound_to_different_text(self) -> None:
        first = await self.runtime.client_commands.submit_typed(**self._submit_args(text="first"))
        await self.runtime.client_commands.wait(first.record.command_id)
        with self.assertRaises(ClientCommandError) as caught:
            await self.runtime.client_commands.submit_typed(**self._submit_args(text="different"))
        self.assertEqual(caught.exception.code, "idempotency-conflict")
        self.assertEqual(self.provider.calls, 1)

    async def test_stale_runtime_or_conversation_is_rejected_before_execution(self) -> None:
        args = self._submit_args()
        with self.assertRaises(ClientCommandError) as runtime_error:
            await self.runtime.client_commands.submit_typed(**{**args, "runtime_id": "runtime-old"})
        self.assertEqual(runtime_error.exception.code, "runtime-changed")

        with self.assertRaises(ClientCommandError) as conversation_error:
            await self.runtime.client_commands.submit_typed(
                **{**args, "conversation_id": "conversation-old"}
            )
        self.assertEqual(conversation_error.exception.code, "conversation-changed")
        self.assertEqual(self.provider.calls, 0)

    async def test_second_client_command_is_rejected_while_foreground_is_busy(self) -> None:
        self.provider.hold = True
        first = await self.runtime.client_commands.submit_typed(**self._submit_args())
        await asyncio.wait_for(self.provider.started.wait(), timeout=1.0)
        with self.assertRaises(ClientCommandError) as caught:
            await self.runtime.client_commands.submit_typed(
                **self._submit_args(request_id="client-request-002", text="second")
            )
        self.assertEqual(caught.exception.code, "foreground-busy")
        self.provider.release.set()
        await self.runtime.client_commands.wait(first.record.command_id)

    async def test_client_can_cancel_its_active_command_through_core_cancellation(self) -> None:
        self.provider.hold = True
        receipt = await self.runtime.client_commands.submit_typed(**self._submit_args())
        await asyncio.wait_for(self.provider.started.wait(), timeout=1.0)
        cancel = await self.runtime.client_commands.cancel(
            command_id=receipt.record.command_id,
            runtime_id=self.runtime.runtime_id,
            conversation_id=self.core.context.conversation_id,
            reason="test cancellation",
        )
        record = await self.runtime.client_commands.wait(receipt.record.command_id)

        self.assertTrue(cancel.accepted)
        self.assertEqual(record.status, ClientCommandStatus.CANCELLED)
        self.assertEqual(self.provider.cancelled_request_ids, [record.trace.request_id])
        event_types = [event.event_type for event in self.runtime.event_bus.history]
        self.assertIn("runtime.client.command.cancel.requested", event_types)
        self.assertIn("turn.cancel.requested", event_types)
        self.assertIn("runtime.client.command.cancelled", event_types)


class RuntimeClientCommandApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.provider = _CommandProvider()
        router = IntelligenceProviderRouter(default_route="primary")
        router.register("primary", self.provider, make_default=True)
        self.runtime = JarvisRuntime(
            settings=RuntimeSettings(event_history_limit=128),
            provider_router=router,
            version="0.0.8-api-test",
        )
        self.runtime.start()
        self.core = self.runtime.create_conversation(
            user_id="api-client-user",
            device_id="api-client-device",
        )
        transport = httpx.ASGITransport(app=create_app(self.runtime))
        self.client = httpx.AsyncClient(transport=transport, base_url="http://test")

    async def asyncTearDown(self) -> None:
        self.provider.release.set()
        await self.client.aclose()
        await asyncio.sleep(0)
        self.runtime.close()

    def _body(self, *, request_id: str = "api-request-001", text: str = "hello") -> dict[str, str]:
        return {
            "runtime_id": self.runtime.runtime_id,
            "conversation_id": self.core.context.conversation_id,
            "client_request_id": request_id,
            "client_id": "api-test-client",
            "text": text,
        }

    async def test_http_submit_ack_exposes_server_trace_and_retry_is_idempotent(self) -> None:
        response = await self.client.post("/v1/runtime/commands/typed", json=self._body())
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["accepted"])
        self.assertFalse(data["duplicate"])
        self.assertTrue(data["trace"]["request_id"].startswith("req-"))
        await self.runtime.client_commands.wait(data["command_id"])

        retry = await self.client.post("/v1/runtime/commands/typed", json=self._body())
        retry_data = retry.json()["data"]
        self.assertTrue(retry_data["duplicate"])
        self.assertEqual(retry_data["command_id"], data["command_id"])
        self.assertEqual(self.provider.calls, 1)

    async def test_http_rejection_is_explicit_protocol_ack(self) -> None:
        response = await self.client.post(
            "/v1/runtime/commands/typed",
            json={**self._body(), "runtime_id": "runtime-stale"},
        )
        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertEqual(body["type"], "client.command.ack")
        self.assertFalse(body["data"]["accepted"])
        self.assertEqual(body["data"]["reason"], "runtime-changed")

    async def test_http_cancel_routes_to_same_authoritative_turn(self) -> None:
        self.provider.hold = True
        submit = await self.client.post("/v1/runtime/commands/typed", json=self._body())
        command_id = submit.json()["data"]["command_id"]
        await asyncio.wait_for(self.provider.started.wait(), timeout=1.0)

        cancel = await self.client.post(
            f"/v1/runtime/commands/{command_id}/cancel",
            json={
                "runtime_id": self.runtime.runtime_id,
                "conversation_id": self.core.context.conversation_id,
                "reason": "api cancellation",
            },
        )
        self.assertEqual(cancel.status_code, 200)
        self.assertEqual(cancel.json()["type"], "client.command.cancel.ack")
        self.assertTrue(cancel.json()["data"]["accepted"])
        record = await self.runtime.client_commands.wait(command_id)
        self.assertEqual(record.status, ClientCommandStatus.CANCELLED)


if __name__ == "__main__":
    unittest.main()
