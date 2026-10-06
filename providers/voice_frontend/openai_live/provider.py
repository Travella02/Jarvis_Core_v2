"""OpenAI GPT-Live full-duplex voice frontend adapter.

This module intentionally implements only the provider transport/session schema.
Jarvis Core owns reasoning, memory, tools, permissions, task state, and client
delegation execution through ``LiveConversationBridge``.
"""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator, Mapping
from typing import Any

import websockets

from core.common.ids import new_id
from core.voice.frontend import (
    VoiceFrontendEvent,
    VoiceFrontendHealth,
    VoiceFrontendMetadata,
    VoiceFrontendProvider,
    VoiceFrontendSession,
    VoiceFrontendSessionConfig,
)
from providers.voice_frontend.openai_live.config import OpenAIGPTLiveConfig
from providers.voice_frontend.openai_live.events import convert_live_event


LIVE_CONVERSATION_INSTRUCTIONS = """You are Jarvis's live conversation layer.
Speak naturally, warmly, and concisely. Sound like a capable human assistant, not a call-center script.

Backchannel policy: Use light natural backchannels when helpful, without talking over the user.

Interruption policy: Stop speaking when the user interrupts and listen to the correction or new request.

Delegation policy:
Backend tools:
- Jarvis Core: reasoning, memory, project context, factual answers, planning, coding, tools, permissions, tasks, and durable state.

Delegate to the backend when:
- A complete user turn needs an answer beyond a brief greeting, acknowledgment, or clarification.
- The answer depends on facts, reasoning, memory, project context, or any action.
- A correction changes work already requested.

Do not delegate to the backend when:
- You are making a very brief natural acknowledgment while backend work is running.
- You need one short clarification before the user's request is complete.

Never invent a backend result or claim an action succeeded before Jarvis Core returns it.
When Jarvis Core returns a result, communicate it naturally and faithfully. Do not contradict or materially change verified facts, permissions, task status, or action outcomes.
"""


class OpenAIGPTLiveSession(VoiceFrontendSession):
    def __init__(self, provider_config: OpenAIGPTLiveConfig, session_config: VoiceFrontendSessionConfig) -> None:
        self.provider_config = provider_config
        self.session_config = session_config
        self._ws: Any | None = None
        self._session_id: str | None = None
        self._event_queue: asyncio.Queue[VoiceFrontendEvent | None] = asyncio.Queue()
        self._reader_task: asyncio.Task[None] | None = None
        self._started = asyncio.Event()
        self._closed = asyncio.Event()
        self._send_lock = asyncio.Lock()
        self._closing = False

    @property
    def session_id(self) -> str | None:
        return self._session_id

    async def start(self) -> None:
        if not self.provider_config.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        self._ws = await websockets.connect(
            self.provider_config.url,
            additional_headers={"Authorization": f"Bearer {self.provider_config.api_key}"},
            open_timeout=self.provider_config.open_timeout_seconds,
            ping_interval=20,
            ping_timeout=20,
            max_size=4_000_000,
        )
        self._reader_task = asyncio.create_task(self._reader(), name="jarvis-gpt-live-reader")
        await self._send(
            {
                "type": "session.start",
                "event_id": new_id("live-start"),
                "session": self._session_payload(),
            }
        )
        try:
            await asyncio.wait_for(self._started.wait(), timeout=self.provider_config.open_timeout_seconds)
        except TimeoutError:
            await self._force_close()
            raise RuntimeError("GPT-Live did not emit session.started before timeout")

    def _session_payload(self) -> dict[str, Any]:
        instructions = self.session_config.instructions.strip() or LIVE_CONVERSATION_INSTRUCTIONS
        payload: dict[str, Any] = {
            "model": self.provider_config.model,
            "instructions": instructions,
            "audio": {
                "format": {"type": "audio/pcm", "rate": self.session_config.sample_rate_hz},
                "output": {"voice": self.session_config.voice},
            },
            "delegation": {"type": "client"},
            "store": bool(self.session_config.store),
        }
        initial = self._serialize_history(self.session_config.history)
        if initial:
            payload["input"] = initial
        return payload

    @staticmethod
    def _serialize_history(history) -> list[dict[str, Any]]:
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

    async def _send(self, payload: Mapping[str, Any]) -> None:
        if self._ws is None:
            raise RuntimeError("GPT-Live session is not connected")
        async with self._send_lock:
            await self._ws.send(json.dumps(dict(payload), separators=(",", ":")))

    async def send_audio(self, pcm_bytes: bytes) -> None:
        if self._closing or not pcm_bytes:
            return
        if len(pcm_bytes) % 2:
            raise ValueError("PCM16 audio must contain complete 16-bit samples")
        await self._send(
            {
                "type": "session.input_audio.append",
                "audio": base64.b64encode(pcm_bytes).decode("ascii"),
            }
        )

    async def send_commentary(self, delegation_id: str, content: str) -> None:
        await self._send_append("session.commentary.append", delegation_id, content)

    async def send_thinking(self, delegation_id: str, content: str) -> None:
        await self._send_append("session.thinking.append", delegation_id, content)

    async def append_instructions(self, content: str) -> None:
        await self._send_append("session.instructions.append", None, content)

    async def _send_append(self, event_type: str, delegation_id: str | None, content: str) -> None:
        clean = content.strip()
        if not clean:
            return
        await self._send(
            {
                "type": event_type,
                "event_id": new_id("live-update"),
                "delegation_id": delegation_id,
                "content": clean,
            }
        )

    async def events(self) -> AsyncIterator[VoiceFrontendEvent]:
        while True:
            item = await self._event_queue.get()
            if item is None:
                return
            yield item

    async def _reader(self) -> None:
        try:
            assert self._ws is not None
            async for raw in self._ws:
                try:
                    payload = json.loads(raw)
                except (TypeError, ValueError):
                    await self._event_queue.put(
                        VoiceFrontendEvent(
                            VoiceFrontendEventType.ERROR,
                            detail="GPT-Live returned invalid JSON",
                            raw_type="invalid-json",
                        )
                    )
                    continue
                event = self._convert_event(payload)
                if event is not None:
                    await self._event_queue.put(event)
                if payload.get("type") == "session.started":
                    session = payload.get("session") if isinstance(payload.get("session"), dict) else {}
                    self._session_id = str(session.get("id") or "") or None
                    self._started.set()
                elif payload.get("type") == "session.closed":
                    self._closed.set()
                    break
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._event_queue.put(
                VoiceFrontendEvent(
                    VoiceFrontendEventType.ERROR,
                    detail=f"GPT-Live connection ended: {type(exc).__name__}",
                    raw_type="transport-error",
                )
            )
        finally:
            self._closed.set()
            await self._event_queue.put(None)

    @staticmethod
    def _convert_event(payload: Mapping[str, Any]) -> VoiceFrontendEvent | None:
        return convert_live_event(payload)

    async def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        if self._ws is None:
            return
        try:
            if not self._closed.is_set():
                await self._send({"type": "session.close", "event_id": new_id("live-close")})
                try:
                    await asyncio.wait_for(self._closed.wait(), timeout=self.provider_config.close_timeout_seconds)
                except TimeoutError:
                    pass
        finally:
            await self._force_close()

    async def _force_close(self) -> None:
        ws = self._ws
        self._ws = None
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass
        if self._reader_task is not None:
            if not self._reader_task.done():
                self._reader_task.cancel()
            await asyncio.gather(self._reader_task, return_exceptions=True)
            self._reader_task = None


class OpenAIGPTLiveProvider(VoiceFrontendProvider):
    def __init__(self, config: OpenAIGPTLiveConfig) -> None:
        self.config = config

    @property
    def metadata(self) -> VoiceFrontendMetadata:
        return VoiceFrontendMetadata(
            provider="openai-gpt-live",
            model=self.config.model,
            local=False,
            full_duplex=True,
            client_delegation=True,
        )

    async def health(self) -> VoiceFrontendHealth:
        if not self.config.api_key:
            return VoiceFrontendHealth("not-configured", "OPENAI_API_KEY is not configured")
        return VoiceFrontendHealth(
            "configured",
            f"{self.config.model} configured for client delegation; no network request performed",
        )

    async def open_session(self, config: VoiceFrontendSessionConfig) -> VoiceFrontendSession:
        if config.sample_rate_hz != self.config.audio_rate_hz:
            raise ValueError(
                f"session sample rate {config.sample_rate_hz} does not match provider rate {self.config.audio_rate_hz}"
            )
        session = OpenAIGPTLiveSession(self.config, config)
        await session.start()
        return session

