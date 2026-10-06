"""OpenAI Realtime WebRTC transport helpers.

The browser owns microphone capture and speaker playback. Jarvis Core owns the
trusted API key and creates the Realtime WebRTC call through the unified
/v1/realtime/calls interface. Tool calls are relayed back to Core over the
localhost control channel; the browser never receives the project API key.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from typing import Any

import httpx

from core.voice.webrtc import normalize_sdp
from providers.voice_frontend.openai_realtime.config import OpenAIRealtimeConfig


DELEGATE_TOOL_NAME = "delegate_to_jarvis_core"

REALTIME_CONVERSATION_INSTRUCTIONS = """You are Jarvis's realtime conversational layer.
Your priority is natural, human conversation: quick turn-taking, useful emotion, concise speech, and immediate interruption handling.

Direct-answer policy:
- Answer ordinary conversation, general knowledge, simple explanations, jokes, and other things you can answer confidently directly.
- Do not pretend to look something up when you already know it. For a simple factual question, answer it naturally instead of saying filler such as 'just a sec'.

Jarvis Core delegation policy:
- Use delegate_to_jarvis_core when the request depends on the user's durable memory, private/project context, files, current application state, permissions, actions, tools, or background tasks.
- Delegate when deeper or longer reasoning would materially improve the answer, or when you are uncertain enough that Jarvis Core should route to a stronger model.
- Preserve the user's constraints faithfully in the delegated request. Never claim a delegated action or result succeeded before Core returns it.

Natural acknowledgement policy:
- A brief acknowledgement such as 'Sure, I'm on it' is appropriate when the user actually asked Jarvis to do work, perform an action, search, coordinate, research, or wait for a result.
- Do not add waiting language before an answer you can give immediately.
- Natural personality is welcome: react with genuine warmth, curiosity, humor, or excitement when it fits the moment. Do not flatten a lively response merely to be terse.
- Do not use personality as filler. A reaction should flow directly into the answer unless real work is actually starting.
- While Core is working, remain available for interruption or follow-up. If asked about a pending result, say that it is still in progress rather than inventing an answer.

When Jarvis Core returns a function result, communicate it naturally and faithfully. Core remains authoritative for memory, permissions, tool outcomes, tasks, and verified facts returned by delegated work.
"""

DELEGATE_TOOL = {
    "type": "function",
    "name": DELEGATE_TOOL_NAME,
    "description": (
        "Delegate work to authoritative Jarvis Core when it requires durable user/project memory, private/current state, "
        "tools or actions, permissions, background work, or stronger/deeper backend reasoning. Do not use this tool for "
        "simple general-knowledge conversation you can answer directly."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "request": {
                "type": "string",
                "description": "A faithful, self-contained description of what the user wants Core to handle, preserving constraints.",
            },
            "mode": {
                "type": "string",
                "enum": ["reasoning", "memory", "action", "long_task"],
                "description": "Why Core is needed. Core remains free to choose the actual model/tool route.",
            },
        },
        "required": ["request", "mode"],
        "additionalProperties": False,
    },
}


class RealtimeWebRTCSessionCreationError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, request_id: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id


def build_realtime_session(config: OpenAIRealtimeConfig) -> dict[str, Any]:
    return {
        "type": "realtime",
        "model": config.model,
        "instructions": REALTIME_CONVERSATION_INSTRUCTIONS,
        "output_modalities": ["audio"],
        "audio": {
            "input": {
                "turn_detection": {
                    "type": "semantic_vad",
                    "create_response": True,
                    "interrupt_response": True,
                }
            },
            "output": {"voice": config.voice},
        },
        "reasoning": {"effort": config.reasoning_effort},
        "tools": [DELEGATE_TOOL],
        "tool_choice": "auto",
    }


async def create_realtime_webrtc_call(
    config: OpenAIRealtimeConfig,
    offer_sdp: str,
    *,
    client: httpx.AsyncClient | None = None,
    url: str | None = None,
) -> tuple[str, str]:
    if not config.api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    clean_sdp = normalize_sdp(offer_sdp, label="Realtime WebRTC SDP offer")
    session_json = json.dumps(build_realtime_session(config), separators=(",", ":"))

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=config.open_timeout_seconds)
    try:
        # OpenAI's Realtime unified WebRTC endpoint expects ordinary
        # multipart *form fields* named ``sdp`` and ``session``. In httpx,
        # giving a tuple a filename turns that part into a file upload. The
        # API does not treat a file part named ``sdp`` as the required string
        # field and rejects the request with ``field \"sdp\" is required``.
        # Keep both parts filename-free so they serialize like FormData.set().
        response = await client.post(
            url or config.webrtc_url,
            headers={"Authorization": f"Bearer {config.api_key}"},
            files={
                "sdp": (None, clean_sdp),
                "session": (None, session_json),
            },
        )
        request_id = response.headers.get("x-request-id")
        if response.status_code >= 400:
            safe_body = response.text[:1600].replace(config.api_key, "[REDACTED]")
            suffix = f" | request_id={request_id}" if request_id else ""
            raise RealtimeWebRTCSessionCreationError(
                f"OpenAI Realtime WebRTC call rejected ({response.status_code}): {safe_body}{suffix}",
                status_code=response.status_code,
                request_id=request_id,
            )
        answer_sdp = normalize_sdp(response.text, label="OpenAI Realtime SDP answer")
        location = response.headers.get("location") or ""
        call_id = location.rstrip("/").split("/")[-1] if location else ""
        if not call_id:
            # A call ID is useful for lifecycle/server controls but the SDP is the
            # only value strictly required to complete WebRTC. Keep a stable local
            # marker rather than failing a working call if a proxy omits Location.
            call_id = request_id or "realtime-webrtc-call"
        return call_id, answer_sdp
    finally:
        if owns_client:
            await client.aclose()


async def hangup_realtime_call(
    config: OpenAIRealtimeConfig,
    call_id: str | None,
    *,
    client: httpx.AsyncClient | None = None,
) -> bool:
    """Best-effort server-side teardown so Live billing/media cannot outlive Jarvis Core."""
    clean = str(call_id or "").strip()
    if not clean or clean == "realtime-webrtc-call" or not config.api_key:
        return False
    base = config.webrtc_url.rsplit("/calls", 1)[0] + "/calls"
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=config.open_timeout_seconds)
    try:
        response = await client.post(
            f"{base}/{clean}/hangup",
            headers={"Authorization": f"Bearer {config.api_key}"},
        )
        return response.status_code < 400
    finally:
        if owns_client:
            await client.aclose()


class BrowserRealtimeRelay:
    """Local control-plane relay for a browser-owned Realtime WebRTC session."""

    def __init__(self) -> None:
        self._call_id: str | None = None
        self._events: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._outgoing: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._closed = False

    @property
    def call_id(self) -> str | None:
        return self._call_id

    def set_call_id(self, call_id: str) -> None:
        clean = call_id.strip()
        if not clean:
            raise ValueError("call_id must be non-empty")
        if self._call_id is not None and self._call_id != clean:
            raise RuntimeError("Realtime call ID cannot change after creation")
        self._call_id = clean

    async def feed_event(self, payload: Mapping[str, Any]) -> None:
        if self._closed:
            return
        await self._events.put(dict(payload))

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            item = await self._events.get()
            if item is None:
                return
            yield item

    async def outgoing(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            item = await self._outgoing.get()
            if item is None:
                return
            yield item

    async def send_function_output(self, call_id: str, output: Mapping[str, Any], *, continue_response: bool = True) -> None:
        if self._closed:
            return
        await self._outgoing.put(
            {
                "kind": "realtime_send",
                "event": {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps(dict(output), separators=(",", ":")),
                    },
                },
            }
        )
        if continue_response:
            await self._outgoing.put({"kind": "realtime_send", "event": {"type": "response.create"}})

    async def request_browser_close(self) -> None:
        if not self._closed:
            await self._outgoing.put({"kind": "lab_command", "command": "close"})

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._events.put(None)
        await self._outgoing.put(None)
