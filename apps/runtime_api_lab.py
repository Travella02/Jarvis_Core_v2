"""0.0.7 real TCP/HTTP/WebSocket reconnect diagnostic.

This lab intentionally uses no microphone, TTS, provider credentials, or external
network. It starts the platform-neutral Runtime API on an ephemeral loopback port,
connects a client, disconnects it, advances the authoritative Core while the client
is gone, and proves cursor-based replay on reconnect.
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
        if cancellation_token.is_cancelled:
            yield IntelligenceEvent(event_type=IntelligenceEventType.CANCELLED)
            return
        yield IntelligenceEvent(
            event_type=IntelligenceEventType.TEXT_DELTA,
            text_delta="Runtime API stayed authoritative while the client was disconnected.",
        )
        yield IntelligenceEvent(
            event_type=IntelligenceEventType.COMPLETED,
            provider_response_id="runtime-api-lab-response",
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
        return None

    async def health(self) -> ProviderHealth:
        return ProviderHealth(ProviderHealthState.HEALTHY, "runtime API lab ready")


async def _recv_json(websocket) -> dict[str, object]:
    raw = await asyncio.wait_for(websocket.recv(), timeout=5.0)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)


async def run(*, emit_json: bool = False) -> int:
    settings = RuntimeSettings(
        event_history_limit=128,
        api_host="127.0.0.1",
        api_port=8766,
        api_heartbeat_seconds=2.0,
    )
    router = IntelligenceProviderRouter(default_route="primary")
    router.register("primary", _ApiLabProvider(), make_default=True)
    runtime = JarvisRuntime(settings=settings, provider_router=router, version="0.0.7-lab")
    runtime.start()
    core = runtime.create_conversation(
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

        params = urlencode(
            {
                "after": first_cursor,
                "runtime_id": runtime_id,
                "client_id": "runtime-api-lab",
                "platform": "ios",
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
            disconnect_cursor = int(ready["data"]["cursor"])

        # Advance authoritative Core state while the UI/client is gone.
        conversation_identity_before = id(runtime.conversation)
        result = await core.submit_typed("client is disconnected")
        if id(runtime.conversation) != conversation_identity_before:
            raise RuntimeError("client disconnect replaced the authoritative Conversation Core")

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
        reconnect_snapshot = reconnect_data["snapshot"]
        if not reconnect_data["resume_accepted"]:
            raise RuntimeError(f"reconnect rejected: {reconnect_data['reset_reason']}")
        if reconnect_snapshot["runtime_id"] != runtime_id:
            raise RuntimeError("runtime identity changed across client restart")
        if reconnect_snapshot["conversation"]["conversation_id"] != conversation_id:
            raise RuntimeError("conversation identity changed across client restart")
        if "turn.endpointed" not in replay_types:
            raise RuntimeError("reconnect replay did not include the missed turn")

        payload = {
            "runtime_id": runtime_id,
            "conversation_id": conversation_id,
            "first_cursor": first_cursor,
            "disconnect_cursor": disconnect_cursor,
            "reconnect_cursor": reconnect_ready["data"]["cursor"],
            "replay_event_count": len(replay_types),
            "replay_event_types": replay_types,
            "turn_status": result.status,
            "turn_text": result.text,
            "core_identity_preserved": id(runtime.conversation) == conversation_identity_before,
            "platform_contract": ["windows", "macos", "linux", "ios", "android"],
            "transport": "loopback HTTP + WebSocket JSON",
            "status": "ok",
        }
        if emit_json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print("Jarvis Core v2 0.0.7 - Runtime API Lab")
            print(f"Runtime: {runtime_id}")
            print(f"Conversation preserved: {'yes' if payload['core_identity_preserved'] else 'no'}")
            print(
                f"Reconnect: cursor={disconnect_cursor} -> {payload['reconnect_cursor']} | "
                f"replayed={payload['replay_event_count']} events"
            )
            print("Client contract: Windows / macOS / Linux / iOS / Android")
            print("Exposure: loopback-only in 0.0.7; authenticated remote transport is deferred")
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
    parser = argparse.ArgumentParser(description="Jarvis Core v2 Runtime API reconnect lab")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)
    return asyncio.run(run(emit_json=args.json))


if __name__ == "__main__":
    raise SystemExit(main())
