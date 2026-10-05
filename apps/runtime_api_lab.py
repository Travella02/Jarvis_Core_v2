"""0.0.8 real Runtime API client-input/reconnect diagnostic.

The lab uses a real loopback Uvicorn server plus HTTP and WebSocket clients. It
proves that a client can submit typed work, retry safely without duplicate model
execution, disconnect/reconnect with replay, and cancel its own active command
while one authoritative JarvisRuntime/Conversation Core remains alive.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import socket
from collections.abc import AsyncIterator, Sequence
from urllib.parse import urlencode

import httpx
import uvicorn
import websockets

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
from core.runtime import IntelligenceProviderRouter, JarvisRuntime, RuntimeSettings
from core.tools import ToolDefinition


class _ApiLabProvider(IntelligenceProvider):
    def __init__(self) -> None:
        self.calls = 0
        self.cancel_calls: list[str] = []
        self.hold_next = False
        self.held_started = asyncio.Event()

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(provider="diagnostic", model="local-api-echo")

    async def stream_response(
        self,
        context: IntelligenceContext,
        tools: Sequence[ToolDefinition],
        reasoning_policy: ReasoningPolicy,
        cancellation_token: CancellationToken,
    ) -> AsyncIterator[IntelligenceEvent]:
        self.calls += 1
        hold = self.hold_next
        self.hold_next = False
        if hold:
            self.held_started.set()
            while not cancellation_token.is_cancelled:
                await asyncio.sleep(0.01)
            yield IntelligenceEvent(
                event_type=IntelligenceEventType.CANCELLED,
                detail=cancellation_token.reason,
            )
            return
        if cancellation_token.is_cancelled:
            yield IntelligenceEvent(event_type=IntelligenceEventType.CANCELLED)
            return
        yield IntelligenceEvent(
            event_type=IntelligenceEventType.TEXT_DELTA,
            text_delta="Runtime API client input stayed inside authoritative Conversation Core.",
        )
        yield IntelligenceEvent(
            event_type=IntelligenceEventType.COMPLETED,
            provider_response_id=f"runtime-api-lab-response-{self.calls}",
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
        self.cancel_calls.append(request_id)

    async def health(self) -> ProviderHealth:
        return ProviderHealth(ProviderHealthState.HEALTHY, "runtime API lab ready")


async def _recv_json(websocket) -> dict[str, object]:
    raw = await asyncio.wait_for(websocket.recv(), timeout=5.0)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)


async def _recv_until_event(websocket, event_type: str) -> tuple[dict[str, object], int]:
    latest_sequence = 0
    for _ in range(128):
        message = await _recv_json(websocket)
        if message.get("type") != "event":
            continue
        event = message["data"]["event"]
        latest_sequence = max(latest_sequence, int(event["sequence"]))
        if event["event_type"] == event_type:
            return event, latest_sequence
    raise RuntimeError(f"did not receive expected event: {event_type}")


def _command_body(
    *,
    runtime_id: str,
    conversation_id: str,
    client_request_id: str,
    text: str,
) -> dict[str, str]:
    return {
        "runtime_id": runtime_id,
        "conversation_id": conversation_id,
        "client_request_id": client_request_id,
        "client_id": "runtime-api-lab",
        "text": text,
    }


async def run(*, emit_json: bool = False) -> int:
    settings = RuntimeSettings(
        event_history_limit=256,
        api_host="127.0.0.1",
        api_port=8766,
        api_heartbeat_seconds=2.0,
    )
    provider = _ApiLabProvider()
    router = IntelligenceProviderRouter(default_route="primary")
    router.register("primary", provider, make_default=True)
    runtime = JarvisRuntime(settings=settings, provider_router=router, version="0.0.8-lab")
    runtime.start()
    runtime.create_conversation(
        user_id="runtime-api-lab-user",
        speaker_id="runtime-api-lab-speaker",
        device_id="runtime-api-lab-device",
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((settings.api_host, 0))
    sock.listen(128)
    sock.setblocking(False)
    port = sock.getsockname()[1]

    app = create_app(runtime)
    config = uvicorn.Config(app, log_level="warning", lifespan="off", access_log=False)
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve(sockets=[sock]))

    try:
        for _ in range(100):
            if server.started:
                break
            if server_task.done():
                await server_task
            await asyncio.sleep(0.02)
        if not server.started:
            raise RuntimeError("Runtime API lab server did not start")

        base_url = f"http://127.0.0.1:{port}"
        async with httpx.AsyncClient(base_url=base_url, timeout=5.0) as client:
            response = await client.get("/v1/runtime/snapshot")
            response.raise_for_status()
            initial = response.json()["data"]
            runtime_id = str(initial["runtime_id"])
            conversation_id = str(initial["conversation"]["conversation_id"])
            first_cursor = int(initial["event_cursor"])
            core_identity_before = id(runtime.conversation)

            params = urlencode(
                {
                    "after": first_cursor,
                    "runtime_id": runtime_id,
                    "client_id": "runtime-api-lab",
                    "platform": "windows",
                    "device_id": "portable-client",
                    "protocol_version": 1,
                }
            )
            ws_url = f"ws://127.0.0.1:{port}/v1/runtime/events/ws?{params}"
            async with websockets.connect(ws_url, open_timeout=5.0) as websocket:
                hello = await _recv_json(websocket)
                sync = await _recv_json(websocket)
                ready = await _recv_json(websocket)
                if hello["type"] != "hello" or sync["type"] != "sync" or ready["type"] != "ready":
                    raise RuntimeError("unexpected Runtime API handshake")
                if not sync["data"]["resume_accepted"]:
                    raise RuntimeError(f"first client resume rejected: {sync['data']['reset_reason']}")

                body = _command_body(
                    runtime_id=runtime_id,
                    conversation_id=conversation_id,
                    client_request_id="lab-request-001",
                    text="submit this through the runtime API",
                )
                submit = await client.post("/v1/runtime/commands/typed", json=body)
                submit.raise_for_status()
                ack = submit.json()["data"]
                if not ack["accepted"] or ack["duplicate"]:
                    raise RuntimeError("typed command was not freshly accepted")
                command_id = str(ack["command_id"])
                request_id = str(ack["trace"]["request_id"])
                completed_event, live_cursor = await _recv_until_event(
                    websocket,
                    "runtime.client.command.completed",
                )
                if completed_event["trace"]["request_id"] != request_id:
                    raise RuntimeError("event stream trace did not match command acknowledgement")

                duplicate = await client.post("/v1/runtime/commands/typed", json=body)
                duplicate.raise_for_status()
                duplicate_ack = duplicate.json()["data"]
                if not duplicate_ack["duplicate"] or duplicate_ack["command_id"] != command_id:
                    raise RuntimeError("retry did not return the same idempotent command")
                if provider.calls != 1:
                    raise RuntimeError("duplicate retry executed the provider more than once")
                disconnect_cursor = live_cursor

            # While the UI is gone, another client request still enters the same Core.
            offline_body = _command_body(
                runtime_id=runtime_id,
                conversation_id=conversation_id,
                client_request_id="lab-request-002",
                text="client is disconnected but core remains authoritative",
            )
            offline_submit = await client.post("/v1/runtime/commands/typed", json=offline_body)
            offline_submit.raise_for_status()
            offline_command_id = str(offline_submit.json()["data"]["command_id"])
            offline_record = await runtime.client_commands.wait(offline_command_id)
            if offline_record.status.value != "completed":
                raise RuntimeError("disconnected client command did not complete")

            params = urlencode(
                {
                    "after": disconnect_cursor,
                    "runtime_id": runtime_id,
                    "client_id": "runtime-api-lab-reconnect",
                    "platform": "android",
                    "device_id": "portable-client",
                    "protocol_version": 1,
                }
            )
            ws_url = f"ws://127.0.0.1:{port}/v1/runtime/events/ws?{params}"
            async with websockets.connect(ws_url, open_timeout=5.0) as websocket:
                await _recv_json(websocket)  # hello
                reconnect_sync = await _recv_json(websocket)
                reconnect_ready = await _recv_json(websocket)

                reconnect_data = reconnect_sync["data"]
                replay_types = [item["event_type"] for item in reconnect_data["replay_events"]]
                if not reconnect_data["resume_accepted"]:
                    raise RuntimeError(f"reconnect rejected: {reconnect_data['reset_reason']}")
                if "runtime.client.command.accepted" not in replay_types:
                    raise RuntimeError("reconnect replay missed client command acceptance")
                if "runtime.client.command.completed" not in replay_types:
                    raise RuntimeError("reconnect replay missed client command completion")

                # Active command cancellation goes through the same Core cancellation path.
                provider.hold_next = True
                provider.held_started.clear()
                cancel_body = _command_body(
                    runtime_id=runtime_id,
                    conversation_id=conversation_id,
                    client_request_id="lab-request-003",
                    text="hold this command until I cancel it",
                )
                cancel_submit = await client.post("/v1/runtime/commands/typed", json=cancel_body)
                cancel_submit.raise_for_status()
                cancel_ack = cancel_submit.json()["data"]
                cancel_command_id = str(cancel_ack["command_id"])
                await asyncio.wait_for(provider.held_started.wait(), timeout=2.0)
                cancel_response = await client.post(
                    f"/v1/runtime/commands/{cancel_command_id}/cancel",
                    json={
                        "runtime_id": runtime_id,
                        "conversation_id": conversation_id,
                        "reason": "runtime API lab cancellation",
                    },
                )
                cancel_response.raise_for_status()
                if not cancel_response.json()["data"]["accepted"]:
                    raise RuntimeError("active client command cancellation was rejected")
                cancelled_record = await runtime.client_commands.wait(cancel_command_id)
                if cancelled_record.status.value != "cancelled":
                    raise RuntimeError("active client command did not reach cancelled status")

            if id(runtime.conversation) != core_identity_before:
                raise RuntimeError("client activity replaced the authoritative Conversation Core")

            payload = {
                "runtime_id": runtime_id,
                "conversation_id": conversation_id,
                "first_cursor": first_cursor,
                "disconnect_cursor": disconnect_cursor,
                "reconnect_cursor": int(reconnect_ready["data"]["cursor"]),
                "replay_event_count": len(replay_types),
                "provider_calls": provider.calls,
                "duplicate_provider_calls": 1,
                "typed_command_id": command_id,
                "offline_command_id": offline_command_id,
                "cancelled_command_id": cancel_command_id,
                "cancel_provider_calls": len(provider.cancel_calls),
                "core_identity_preserved": id(runtime.conversation) == core_identity_before,
                "platform_contract": ["windows", "macos", "linux", "ios", "android"],
                "transport": "loopback HTTP + WebSocket JSON",
                "status": "ok",
            }
            if emit_json:
                print(json.dumps(payload, indent=2, sort_keys=True))
            else:
                print("Jarvis Core v2 0.0.8 - Client Input & Runtime Control Lab")
                print(f"Runtime: {runtime_id}")
                print(f"Conversation preserved: {'yes' if payload['core_identity_preserved'] else 'no'}")
                print("Typed command: accepted through HTTP and correlated on the event stream")
                print("Retry safety: duplicate client_request_id executed provider once")
                print(
                    f"Reconnect: cursor={disconnect_cursor} -> {payload['reconnect_cursor']} | "
                    f"replayed={payload['replay_event_count']} events"
                )
                print("Cancellation: active client command cancelled through Conversation Core")
                print("Exposure: loopback-only; authenticated remote transport remains deferred")
                print("Status: ok")
            return 0
    finally:
        server.should_exit = True
        with suppress_exception(asyncio.CancelledError):
            await asyncio.wait_for(server_task, timeout=5.0)
        sock.close()
        runtime.close()


class suppress_exception:
    def __init__(self, *exceptions: type[BaseException]) -> None:
        self.exceptions = exceptions

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return exc_type is not None and issubclass(exc_type, self.exceptions)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Jarvis Core v2 client input/runtime control lab")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)
    return asyncio.run(run(emit_json=args.json))


if __name__ == "__main__":
    raise SystemExit(main())
