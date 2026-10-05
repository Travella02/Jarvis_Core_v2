"""Platform-neutral local Jarvis Runtime API.

The API is an adapter over an already-owned :class:`JarvisRuntime`. It never
creates a second Conversation Core and never derives authoritative product state
from the client connection itself.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect

from core.runtime import JarvisRuntime
from core.runtime.client_stream import RuntimeEventStream
from core.runtime.protocol import (
    API_PREFIX,
    PROTOCOL_NAME,
    PROTOCOL_VERSION,
    envelope,
    event_batch_to_dict,
    event_to_dict,
    protocol_description,
    snapshot_to_dict,
)


def create_app(runtime: JarvisRuntime) -> FastAPI:
    """Create the HTTP/WebSocket adapter for one authoritative runtime.

    Lifecycle ownership remains outside this function. This is deliberate: V1
    taught us that UI/server helpers must not quietly create or restart a second
    Core process when another owner already exists.
    """

    app = FastAPI(title="Jarvis Runtime API", version=runtime.version)
    app.state.jarvis_runtime = runtime

    @app.get(f"{API_PREFIX}/protocol")
    async def protocol() -> dict[str, Any]:
        return envelope("protocol", data=protocol_description())

    @app.get(f"{API_PREFIX}/health")
    async def health() -> dict[str, Any]:
        snap = runtime.snapshot()
        return envelope(
            "health",
            data={
                "runtime_id": snap.runtime_id,
                "version": snap.version,
                "lifecycle": snap.lifecycle.value,
                "health": snap.health.state.value,
                "event_cursor": snap.event_cursor,
            },
        )

    @app.get(f"{API_PREFIX}/runtime/snapshot")
    async def runtime_snapshot() -> dict[str, Any]:
        return envelope("runtime.snapshot", data=snapshot_to_dict(runtime.snapshot()))

    @app.get(f"{API_PREFIX}/runtime/events")
    async def runtime_events(
        after: int = Query(default=0, ge=0),
        limit: int | None = Query(default=None, ge=1),
        runtime_id: str = Query(default="", max_length=200),
    ) -> dict[str, Any]:
        requested_limit = min(256, runtime.settings.api_max_replay_events) if limit is None else limit
        if requested_limit > runtime.settings.api_max_replay_events:
            raise HTTPException(
                status_code=400,
                detail=f"limit must be <= {runtime.settings.api_max_replay_events}",
            )
        snap = runtime.snapshot()
        expected_runtime_id = runtime_id.strip() or None
        reset_reason: str | None = None
        if after > 0 and expected_runtime_id is None:
            reset_reason = "runtime-identity-required"
        elif expected_runtime_id is not None and expected_runtime_id != snap.runtime_id:
            reset_reason = "runtime-changed"
        elif after > snap.event_cursor:
            reset_reason = "cursor-ahead"

        batch = runtime.events_after(after, limit=requested_limit)
        if reset_reason is None and batch.gap_detected:
            reset_reason = "history-gap"

        data = event_batch_to_dict(batch)
        data.update(
            {
                "runtime_id": snap.runtime_id,
                "resume_accepted": reset_reason is None,
                "reset_reason": reset_reason,
                "snapshot_cursor": snap.event_cursor,
            }
        )
        if reset_reason is not None:
            data["events"] = []
        return envelope("runtime.events", data=data)

    @app.websocket(f"{API_PREFIX}/runtime/events/ws")
    async def runtime_events_socket(
        websocket: WebSocket,
        after: int = Query(default=0, ge=0),
        runtime_id: str = Query(default="", max_length=200),
        client_id: str = Query(default="client", min_length=1, max_length=120),
        platform: str = Query(default="unknown", min_length=1, max_length=40),
        device_id: str = Query(default="", max_length=160),
        protocol_version: int = Query(default=PROTOCOL_VERSION, ge=1),
    ) -> None:
        if protocol_version != PROTOCOL_VERSION:
            await websocket.close(code=1008, reason="unsupported protocol version")
            return

        await websocket.accept()
        stream = RuntimeEventStream(
            runtime,
            queue_limit=runtime.settings.api_event_queue_limit,
            max_replay_events=runtime.settings.api_max_replay_events,
        )
        try:
            sync = await stream.open(
                after_sequence=after,
                expected_runtime_id=runtime_id or None,
            )
            await websocket.send_json(
                envelope(
                    "hello",
                    data={
                        "protocol": PROTOCOL_NAME,
                        "protocol_version": PROTOCOL_VERSION,
                        "runtime_id": sync.snapshot.runtime_id,
                        "client_id": client_id,
                        "device_id": device_id or None,
                        "platform": platform,
                        "platform_is_informational": True,
                    },
                )
            )
            await websocket.send_json(
                envelope(
                    "sync",
                    data={
                        "runtime_id": sync.snapshot.runtime_id,
                        "requested_after": sync.requested_after,
                        "resume_accepted": sync.resume_accepted,
                        "reset_reason": sync.reset_reason,
                        "snapshot": snapshot_to_dict(sync.snapshot),
                        "replay_events": [event_to_dict(event) for event in sync.replay_events],
                    },
                )
            )
            await websocket.send_json(
                envelope(
                    "ready",
                    data={
                        "runtime_id": sync.snapshot.runtime_id,
                        "cursor": sync.snapshot.event_cursor,
                    },
                )
            )

            while True:
                event_task = asyncio.create_task(stream.next_event())
                receive_task = asyncio.create_task(websocket.receive())
                done, pending = await asyncio.wait(
                    {event_task, receive_task},
                    timeout=runtime.settings.api_heartbeat_seconds,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                for task in pending:
                    with suppress(asyncio.CancelledError):
                        await task

                if not done:
                    await websocket.send_json(
                        envelope(
                            "heartbeat",
                            data={
                                "runtime_id": runtime.runtime_id,
                                "cursor": stream.last_sequence,
                            },
                        )
                    )
                    continue

                if receive_task in done:
                    message = receive_task.result()
                    if message.get("type") == "websocket.disconnect":
                        break
                    payload = message.get("text")
                    if payload == "ping":
                        await websocket.send_json(
                            envelope(
                                "pong",
                                data={"runtime_id": runtime.runtime_id, "cursor": stream.last_sequence},
                            )
                        )

                if event_task in done:
                    event = event_task.result()
                    if stream.overflowed:
                        snap = runtime.snapshot()
                        await websocket.send_json(
                            envelope(
                                "resync-required",
                                data={
                                    "reason": "client-backpressure",
                                    "runtime_id": snap.runtime_id,
                                    "snapshot": snapshot_to_dict(snap),
                                },
                            )
                        )
                        await websocket.close(code=1013, reason="client must resync")
                        break
                    await websocket.send_json(
                        envelope("event", data={"event": event_to_dict(event)})
                    )
        except WebSocketDisconnect:
            pass
        finally:
            await stream.close()

    return app


__all__ = ["create_app"]
