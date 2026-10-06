"""Shared GPT-Live event normalization.

Both the server-owned WebSocket transport and the browser WebRTC relay emit the
same Live JSON event schema.  Keeping translation here prevents transport
choices from leaking into Jarvis Core or the conversation bridge.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from typing import Any

from core.voice.frontend import VoiceFrontendEvent, VoiceFrontendEventType


def convert_live_event(payload: Mapping[str, Any]) -> VoiceFrontendEvent | None:
    event_type = str(payload.get("type") or "")
    if event_type == "session.started":
        return VoiceFrontendEvent(VoiceFrontendEventType.SESSION_STARTED, raw_type=event_type)
    if event_type == "session.input_transcript.delta":
        return VoiceFrontendEvent(
            VoiceFrontendEventType.INPUT_TRANSCRIPT_DELTA,
            text=str(payload.get("delta") or ""),
            start_ms=_int_or_none(payload.get("start_ms")),
            end_ms=_int_or_none(payload.get("end_ms")),
            raw_type=event_type,
        )
    if event_type == "session.output_transcript.delta":
        return VoiceFrontendEvent(
            VoiceFrontendEventType.OUTPUT_TRANSCRIPT_DELTA,
            text=str(payload.get("delta") or ""),
            start_ms=_int_or_none(payload.get("start_ms")),
            end_ms=_int_or_none(payload.get("end_ms")),
            raw_type=event_type,
        )
    if event_type == "session.output_audio.delta":
        try:
            audio = base64.b64decode(str(payload.get("delta") or ""), validate=True)
        except Exception:
            return VoiceFrontendEvent(
                VoiceFrontendEventType.ERROR,
                detail="GPT-Live returned invalid base64 audio",
                raw_type=event_type,
            )
        return VoiceFrontendEvent(VoiceFrontendEventType.OUTPUT_AUDIO, audio=audio, raw_type=event_type)
    if event_type == "session.delegation.created":
        delegation = payload.get("delegation") if isinstance(payload.get("delegation"), dict) else {}
        if str(delegation.get("target") or "") != "client":
            return None
        return VoiceFrontendEvent(
            VoiceFrontendEventType.DELEGATION_REQUESTED,
            delegation_id=str(delegation.get("id") or "") or None,
            offset_ms=_int_or_none(payload.get("offset_ms")),
            raw_type=event_type,
        )
    if event_type == "session.usage.updated":
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        seconds = usage.get("seconds")
        return VoiceFrontendEvent(
            VoiceFrontendEventType.USAGE_UPDATED,
            usage_seconds=float(seconds) if isinstance(seconds, (int, float)) else None,
            raw_type=event_type,
        )
    if event_type == "session.closed":
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        seconds = usage.get("seconds")
        return VoiceFrontendEvent(
            VoiceFrontendEventType.SESSION_CLOSED,
            usage_seconds=float(seconds) if isinstance(seconds, (int, float)) else None,
            raw_type=event_type,
        )
    if event_type == "error":
        error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
        return VoiceFrontendEvent(
            VoiceFrontendEventType.ERROR,
            detail=str(error.get("message") or "GPT-Live returned an error"),
            raw_type=event_type,
        )
    if event_type == "info":
        return VoiceFrontendEvent(
            VoiceFrontendEventType.INFO,
            detail=str(payload.get("message") or ""),
            raw_type=event_type,
        )
    return None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return max(0, int(value))
    return None
