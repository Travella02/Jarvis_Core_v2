"""Versioned, platform-neutral runtime client protocol.

The client contract remains independent of Electron, Windows, Python object
layouts, and provider-specific state. Native Windows/macOS/iOS/Android clients
consume the same JSON representation over HTTP/WebSocket. 0.0.8 adds typed
client requests without transferring state or trace authority to the client.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from core.common.ids import CorrelationContext
from core.conversation import CoreEvent
from core.runtime.models import EventBatch, RuntimeSnapshot


PROTOCOL_NAME = "jarvis-runtime"
PROTOCOL_VERSION = 1
API_PREFIX = "/v1"


class RuntimeProtocolError(ValueError):
    pass


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_value(value: Any) -> Any:
    """Convert supported runtime values into deterministic JSON-safe values.

    Network protocol values are intentionally narrow. In particular bytes and
    arbitrary objects are rejected instead of being stringified, which avoids
    accidentally leaking opaque provider/native state through the public API.
    """

    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, datetime):
        return _timestamp(value)
    if isinstance(value, Enum):
        return _json_value(value.value)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise RuntimeProtocolError("runtime protocol mapping keys must be strings")
            result[key] = _json_value(item)
        return result
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if is_dataclass(value):
        return _json_value(asdict(value))
    raise RuntimeProtocolError(
        f"unsupported runtime protocol value type: {type(value).__name__}"
    )


def trace_to_dict(trace: CorrelationContext | None) -> dict[str, str | None] | None:
    if trace is None:
        return None
    return {
        "correlation_id": trace.correlation_id,
        "request_id": trace.request_id,
        "turn_id": trace.turn_id,
        "cancellation_id": trace.cancellation_id,
    }


def event_to_dict(event: CoreEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "timestamp": _timestamp(event.timestamp),
        "origin": event.origin,
        "sequence": event.sequence,
        "trace": trace_to_dict(event.trace),
        "conversation_id": event.conversation_id,
        "user_id": event.user_id,
        "device_id": event.device_id,
        "task_id": event.task_id,
        "parent_event_id": event.parent_event_id,
        "payload": _json_value(event.payload),
    }


def health_to_dict(snapshot) -> dict[str, Any]:
    return {
        "state": snapshot.state.value,
        "components": {
            name: {
                "name": item.name,
                "state": item.state.value,
                "detail": item.detail,
                "critical": item.critical,
                "updated_at": _timestamp(item.updated_at),
            }
            for name, item in sorted(snapshot.components.items())
        },
    }


def snapshot_to_dict(snapshot: RuntimeSnapshot) -> dict[str, Any]:
    conversation = snapshot.conversation
    return {
        "runtime_id": snapshot.runtime_id,
        "version": snapshot.version,
        "lifecycle": snapshot.lifecycle.value,
        "health": health_to_dict(snapshot.health),
        "started_at": _timestamp(snapshot.started_at) if snapshot.started_at else None,
        "uptime_ms": round(float(snapshot.uptime_ms), 3),
        "event_cursor": snapshot.event_cursor,
        "oldest_event_sequence": snapshot.oldest_event_sequence,
        "settings": _json_value(snapshot.settings),
        "conversation": (
            {
                "conversation_id": conversation.conversation_id,
                "activity_state": conversation.activity_state,
                "presence_state": conversation.presence_state,
                "transcript_entries": conversation.transcript_entries,
                "active_turn_id": conversation.active_turn_id,
            }
            if conversation is not None
            else None
        ),
    }


def event_batch_to_dict(batch: EventBatch) -> dict[str, Any]:
    return {
        "after_sequence": batch.after_sequence,
        "latest_sequence": batch.latest_sequence,
        "oldest_available_sequence": batch.oldest_available_sequence,
        "gap_detected": batch.gap_detected,
        "events": [event_to_dict(event) for event in batch.events],
    }


def envelope(message_type: str, *, data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not message_type.strip():
        raise RuntimeProtocolError("message_type must be non-empty")
    return {
        "protocol": PROTOCOL_NAME,
        "protocol_version": PROTOCOL_VERSION,
        "type": message_type,
        "data": _json_value(data or {}),
    }


def protocol_description() -> dict[str, Any]:
    """Public capability description for native clients.

    The platform names are descriptive only. Server behavior never changes based
    on a caller claiming one of these values.
    """

    return {
        "name": PROTOCOL_NAME,
        "version": PROTOCOL_VERSION,
        "transports": ["http-json", "websocket-json"],
        "client_platforms": ["windows", "macos", "linux", "ios", "android"],
        "cursor_authority": "runtime-id-plus-event-sequence",
        "state_authority": "runtime-snapshot",
        "remote_transport": "deferred-authenticated-transport",
        "client_input": {
            "typed_command": f"POST {API_PREFIX}/runtime/commands/typed",
            "cancel_command": f"POST {API_PREFIX}/runtime/commands/{{command_id}}/cancel",
            "result_delivery": "authoritative-event-stream",
            "idempotency": "runtime-scoped-client-request-id",
        },
    }


__all__ = [
    "API_PREFIX",
    "PROTOCOL_NAME",
    "PROTOCOL_VERSION",
    "RuntimeProtocolError",
    "envelope",
    "event_batch_to_dict",
    "event_to_dict",
    "protocol_description",
    "snapshot_to_dict",
    "trace_to_dict",
]
