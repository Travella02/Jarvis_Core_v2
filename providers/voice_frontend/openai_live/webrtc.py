"""Browser WebRTC transport helpers for GPT-Live.

The browser owns microphone capture, remote audio playout, media jitter handling,
and format negotiation. Jarvis Core remains on the trusted Python side and only
receives normalized transcript/delegation events through a localhost relay.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

import httpx

from core.common.ids import new_id
from core.voice.frontend import VoiceFrontendEvent, VoiceFrontendSession, VoiceFrontendSessionConfig
from core.voice.webrtc import normalize_sdp
from providers.voice_frontend.openai_live.config import OpenAIGPTLiveConfig
from providers.voice_frontend.openai_live.events import convert_live_event
from providers.voice_frontend.openai_live.provider import LIVE_CONVERSATION_INSTRUCTIONS

DEFAULT_WEBRTC_URL = "https://api.openai.com/v1/live/sessions"


class GPTLiveWebRTCSessionCreationError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, request_id: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id


def serialize_history(history: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in history:
        role = str(item.get("role") or "").strip().lower()
        text = str(item.get("content") or "").strip()
        if role not in {"developer", "user", "assistant"} or not text:
            continue
        content_type = "output_text" if role == "assistant" else "input_text"
        result.append(
            {
                "type": "message",
                "role": role,
                "content": [{"type": content_type, "text": text}],
            }
        )
    return result


def build_webrtc_create_payload(
    provider_config: OpenAIGPTLiveConfig,
    session_config: VoiceFrontendSessionConfig,
    offer_sdp: str,
) -> dict[str, Any]:
    clean_sdp = normalize_sdp(offer_sdp, label="WebRTC SDP offer")
    instructions = session_config.instructions.strip() or LIVE_CONVERSATION_INSTRUCTIONS
    session: dict[str, Any] = {
        "model": provider_config.model,
        "instructions": instructions,
        # WebRTC negotiates the media format. Do not pin audio.format here.
        "audio": {"output": {"voice": session_config.voice}},
        "delegation": {"type": "client"},
        "store": bool(session_config.store),
    }
    history = serialize_history(session_config.history)
    if history:
        session["input"] = history
    return {
        "session": session,
        "transport": {"type": "webrtc", "sdp": clean_sdp},
    }


async def create_webrtc_session(
    provider_config: OpenAIGPTLiveConfig,
    session_config: VoiceFrontendSessionConfig,
    offer_sdp: str,
    *,
    client: httpx.AsyncClient | None = None,
    url: str | None = None,
) -> tuple[str, str]:
    if not provider_config.api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    payload = build_webrtc_create_payload(provider_config, session_config, offer_sdp)
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=provider_config.open_timeout_seconds)
    try:
        response = await client.post(
            url or provider_config.webrtc_url,
            headers={
                "Authorization": f"Bearer {provider_config.api_key}",
                "Accept": "application/json",
            },
            json=payload,
        )
        request_id = response.headers.get("x-request-id")
        if response.status_code >= 400:
            safe_body = response.text[:1600].replace(provider_config.api_key, "[REDACTED]")
            suffix = f" | request_id={request_id}" if request_id else ""
            raise GPTLiveWebRTCSessionCreationError(
                f"OpenAI GPT-Live WebRTC session rejected ({response.status_code}): {safe_body}{suffix}",
                status_code=response.status_code,
                request_id=request_id,
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise GPTLiveWebRTCSessionCreationError(
                "OpenAI GPT-Live WebRTC session returned non-JSON success payload",
                status_code=response.status_code,
                request_id=request_id,
            ) from exc
    finally:
        if owns_client:
            await client.aclose()

    session = body.get("session") if isinstance(body, dict) else None
    transport = body.get("transport") if isinstance(body, dict) else None
    session_id = str(session.get("id") or "") if isinstance(session, dict) else ""
    raw_answer_sdp = str(transport.get("sdp") or "") if isinstance(transport, dict) else ""
    if not session_id or not raw_answer_sdp:
        raise RuntimeError("GPT-Live WebRTC session response was missing session.id or transport.sdp")
    answer_sdp = normalize_sdp(raw_answer_sdp, label="OpenAI GPT-Live SDP answer")
    return session_id, answer_sdp


class BrowserWebRTCRelaySession(VoiceFrontendSession):
    """Control-plane proxy for a browser-owned GPT-Live WebRTC connection.

    Audio never enters Python. The browser sends/receives media through WebRTC.
    The localhost control socket forwards only Live JSON events and backend
    commentary between the browser data channel and Jarvis Core.
    """

    def __init__(self) -> None:
        self._session_id: str | None = None
        self._events: asyncio.Queue[VoiceFrontendEvent | None] = asyncio.Queue()
        self._outgoing: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._closed = False

    @property
    def session_id(self) -> str | None:
        return self._session_id

    def set_session_id(self, session_id: str) -> None:
        clean = session_id.strip()
        if not clean:
            raise ValueError("session_id must be non-empty")
        if self._session_id is not None and self._session_id != clean:
            raise RuntimeError("WebRTC relay session ID cannot change after creation")
        self._session_id = clean

    async def feed_live_event(self, payload: Mapping[str, Any]) -> None:
        if self._closed:
            return
        event = convert_live_event(payload)
        if event is not None:
            await self._events.put(event)

    async def send_audio(self, pcm_bytes: bytes) -> None:
        raise RuntimeError("WebRTC audio travels on negotiated browser media tracks, not through Jarvis Core")

    async def send_commentary(self, delegation_id: str, content: str) -> None:
        await self._queue_append("session.commentary.append", delegation_id, content)

    async def send_thinking(self, delegation_id: str, content: str) -> None:
        await self._queue_append("session.thinking.append", delegation_id, content)

    async def append_instructions(self, content: str) -> None:
        await self._queue_append("session.instructions.append", None, content)

    async def _queue_append(self, event_type: str, delegation_id: str | None, content: str) -> None:
        clean = content.strip()
        if not clean or self._closed:
            return
        await self._outgoing.put(
            {
                "kind": "live_send",
                "event": {
                    "type": event_type,
                    "event_id": new_id("live-update"),
                    "delegation_id": delegation_id,
                    "content": clean,
                },
            }
        )

    async def outgoing(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            item = await self._outgoing.get()
            if item is None:
                return
            yield item

    async def events(self) -> AsyncIterator[VoiceFrontendEvent]:
        while True:
            item = await self._events.get()
            if item is None:
                return
            yield item

    async def request_browser_close(self) -> None:
        if not self._closed:
            await self._outgoing.put({"kind": "lab_command", "command": "close"})

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._events.put(None)
        await self._outgoing.put(None)
