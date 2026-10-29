from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import Any, Mapping
from uuid import uuid4

from fastapi import WebSocket

# Ported from read-only v1 0.3.6 BrowserBridge. V2 Core alone owns tool authority.
# Keep executor operations strictly bounded; never expose a general page-action API.
_BRIDGE_ALLOWED = frozenset({"tabs_list", "snapshot", "tab_switch", "navigate", "tab_close", "back", "forward", "refresh", "media_control", "media_volume", "media_mute", "media_fullscreen", "scroll"})


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BrowserBridgeError(RuntimeError):
    pass


class BrowserBridgeDisconnected(BrowserBridgeError):
    pass


class BrowserCommandError(BrowserBridgeError):
    pass


@dataclass(slots=True)
class BrowserBridgeClient:
    websocket: WebSocket
    instance_id: str
    browser_name: str = "Chromium"
    browser_version: str = ""
    extension_version: str = ""
    capabilities: tuple[str, ...] = ()
    connected_at: str = ""
    connected_monotonic: float = 0.0
    last_seen_monotonic: float = 0.0
    active_tab: dict[str, Any] | None = None

    def public(self) -> dict[str, Any]:
        now = time.monotonic()
        return {
            "connected": True,
            "instance_id": self.instance_id,
            "browser_name": self.browser_name,
            "browser_version": self.browser_version,
            "extension_version": self.extension_version,
            "capabilities": list(self.capabilities),
            "connected_at": self.connected_at,
            "last_seen_seconds_ago": round(max(0.0, now - self.last_seen_monotonic), 3),
            "active_tab": dict(self.active_tab or {}),
        }


class BrowserBridge:
    """Loopback-only command bridge to the Jarvis Chromium extension.

    The extension owns browser APIs/DOM access. The Python core only sends bounded,
    typed commands and waits for structured results. Web content never receives the
    trusted desktop header and cannot invoke this bridge directly.
    """

    def __init__(self) -> None:
        self._client: BrowserBridgeClient | None = None
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._send_lock = asyncio.Lock()
        self._state_lock = asyncio.Lock()
        self._last_error = ""

    @staticmethod
    def _clean_text(value: Any, *, maximum: int = 240) -> str:
        text = str(value or "").strip()
        return text[:maximum]

    async def attach(self, websocket: WebSocket, hello: Mapping[str, Any]) -> BrowserBridgeClient:
        instance_id = self._clean_text(hello.get("instance_id"), maximum=160) or str(uuid4())
        client = BrowserBridgeClient(
            websocket=websocket,
            instance_id=instance_id,
            browser_name=self._clean_text(hello.get("browser_name"), maximum=80) or "Chromium",
            browser_version=self._clean_text(hello.get("browser_version"), maximum=80),
            extension_version=self._clean_text(hello.get("extension_version"), maximum=80),
            capabilities=tuple(sorted({self._clean_text(item, maximum=80) for item in (hello.get("capabilities") or []) if self._clean_text(item, maximum=80)})) if isinstance(hello.get("capabilities"), list) else (),
            connected_at=_utc_iso(),
            connected_monotonic=time.monotonic(),
            last_seen_monotonic=time.monotonic(),
            active_tab=dict(hello.get("active_tab") or {}) if isinstance(hello.get("active_tab"), Mapping) else None,
        )
        async with self._state_lock:
            prior = self._client
            self._client = client
            self._last_error = ""
        if prior is not None and prior.websocket is not websocket:
            try:
                await prior.websocket.close(code=1012)
            except Exception:
                pass
        return client

    async def detach(self, websocket: WebSocket, *, reason: str = "disconnected") -> None:
        async with self._state_lock:
            client = self._client
            if client is None or client.websocket is not websocket:
                return
            self._client = None
            self._last_error = reason
            pending = list(self._pending.values())
            self._pending.clear()
        for future in pending:
            if not future.done():
                future.set_exception(BrowserBridgeDisconnected("Browser Bridge disconnected"))

    async def handle_message(self, websocket: WebSocket, message: Mapping[str, Any]) -> None:
        message_type = str(message.get("type") or "").strip().lower()
        async with self._state_lock:
            client = self._client
            if client is not None and client.websocket is websocket:
                client.last_seen_monotonic = time.monotonic()
                active_tab = message.get("active_tab")
                if isinstance(active_tab, Mapping):
                    client.active_tab = dict(active_tab)
                if message_type == "hello":
                    client.browser_name = self._clean_text(message.get("browser_name"), maximum=80) or client.browser_name
                    client.browser_version = self._clean_text(message.get("browser_version"), maximum=80) or client.browser_version
                    client.extension_version = self._clean_text(message.get("extension_version"), maximum=80) or client.extension_version
                    if isinstance(message.get("capabilities"), list):
                        client.capabilities = tuple(sorted({self._clean_text(item, maximum=80) for item in message.get("capabilities") if self._clean_text(item, maximum=80)}))

        if message_type != "result":
            return
        command_id = str(message.get("id") or "").strip()
        if not command_id:
            return
        future = self._pending.pop(command_id, None)
        if future is None or future.done():
            return
        payload = message.get("result")
        result = dict(payload) if isinstance(payload, Mapping) else {}
        if bool(message.get("ok", result.get("ok", False))):
            result.setdefault("ok", True)
            future.set_result(result)
        else:
            error = self._clean_text(message.get("error") or result.get("error") or "Browser command failed", maximum=1000)
            future.set_exception(BrowserCommandError(error))

    def status(self) -> dict[str, Any]:
        client = self._client
        if client is None:
            return {
                "connected": False,
                "browser_name": "",
                "browser_version": "",
                "extension_version": "",
                "capabilities": [],
                "active_tab": {},
                "last_error": self._last_error,
            }
        payload = client.public()
        payload["last_error"] = self._last_error
        return payload

    async def execute(
        self,
        operation: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        timeout_seconds: float = 12.0,
        task_id: str = "",
    ) -> dict[str, Any]:
        operation = str(operation or "").strip().lower()
        if operation not in _BRIDGE_ALLOWED:
            raise ValueError("browser operation is not authorized by the v2 bridge")
        client = self._client
        if client is None:
            raise BrowserBridgeDisconnected("Jarvis Browser Bridge is not connected")
        command_id = str(uuid4())
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[command_id] = future
        command = {
            "type": "command",
            "id": command_id,
            "task_id": str(task_id or ""),
            "operation": operation,
            "arguments": dict(arguments or {}),
        }
        try:
            async with self._send_lock:
                current = self._client
                if current is None or current.websocket is not client.websocket:
                    raise BrowserBridgeDisconnected("Jarvis Browser Bridge changed connections")
                await current.websocket.send_json(command)
            result = await asyncio.wait_for(future, timeout=max(1.0, float(timeout_seconds)))
            current = self._client
            if current is not None:
                current.last_seen_monotonic = time.monotonic()
                active_tab = result.get("active_tab")
                if isinstance(active_tab, Mapping):
                    current.active_tab = dict(active_tab)
            return result
        except TimeoutError as exc:
            self._pending.pop(command_id, None)
            if not future.done():
                future.cancel()
            raise BrowserBridgeError(f"Browser command '{operation}' timed out") from exc
        except Exception:
            self._pending.pop(command_id, None)
            if not future.done():
                future.cancel()
            raise

    async def close(self) -> None:
        client = self._client
        if client is not None:
            try:
                await client.websocket.close(code=1001)
            except Exception:
                pass
            await self.detach(client.websocket, reason="core_shutdown")
