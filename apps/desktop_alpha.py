"""Jarvis Core v2 0.1.0 desktop alpha host.

Electron owns native desktop lifecycle. This loopback Python host owns the one
JarvisRuntime, Realtime WebRTC session brokering, and Core delegation bridge.
The React renderer is intentionally thin and never receives the OpenAI API key
or becomes authoritative for memory, tools, permissions, tasks, or backend
routing.
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager, suppress
from dataclasses import replace
import json
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
import uvicorn

from apps.runtime_api import create_app as create_runtime_api
from core.runtime import IntelligenceProviderRouter, JarvisRuntime, RuntimeSettings
from providers.intelligence.openai import OpenAIProvider, OpenAIProviderConfig
from providers.voice_frontend.openai_realtime import (
    BrowserRealtimeRelay,
    OpenAIRealtimeConfig,
    RealtimeCoreBridge,
    create_realtime_webrtc_call,
    hangup_realtime_call,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATIC_DIR = PROJECT_ROOT / "apps" / "desktop" / "dist"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Jarvis Core v2 0.1.0 Desktop Alpha host")
    result.add_argument("--host", default="127.0.0.1")
    result.add_argument("--port", type=int, default=8765)
    result.add_argument("--static-dir", type=Path, default=DEFAULT_STATIC_DIR)
    return result


def build_runtime() -> tuple[JarvisRuntime, OpenAIProvider]:
    intelligence_config = OpenAIProviderConfig.from_env(env_file=PROJECT_ROOT / ".env")
    # Keep backend intelligence independent from the client-facing WebRTC
    # transport. Luna remains today's delegated route, not a desktop concern.
    intelligence_config = replace(intelligence_config, voice_transport="websocket")
    provider = OpenAIProvider(intelligence_config)
    runtime_settings = RuntimeSettings.from_env(env_file=PROJECT_ROOT / ".env")
    router = IntelligenceProviderRouter(default_route=runtime_settings.default_intelligence_route)
    router.register(runtime_settings.default_intelligence_route, provider, make_default=True)
    runtime = JarvisRuntime(settings=runtime_settings, provider_router=router)
    runtime.start()
    runtime.create_conversation(
        user_id="local-development-user",
        speaker_id="desktop-alpha-user",
        device_id="desktop-alpha",
    )
    return runtime, provider


class DesktopRealtimeSession:
    """Own one renderer Realtime session without giving the renderer Core authority."""

    def __init__(self, *, runtime: JarvisRuntime, config: OpenAIRealtimeConfig) -> None:
        if runtime.conversation is None:
            raise RuntimeError("JarvisRuntime conversation must exist before desktop voice starts")
        self.runtime = runtime
        self.config = config
        self._relay: BrowserRealtimeRelay | None = None
        self._bridge: RealtimeCoreBridge | None = None
        self._event_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    @property
    def active(self) -> bool:
        return self._relay is not None

    @property
    def call_id(self) -> str | None:
        return self._relay.call_id if self._relay is not None else None

    async def open_control(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            if self._relay is not None:
                await websocket.close(code=1013, reason="desktop realtime session already active")
                return
            relay = BrowserRealtimeRelay()
            bridge = RealtimeCoreBridge(conversation=self.runtime.conversation, relay=relay)
            self._relay = relay
            self._bridge = bridge
            self._event_task = asyncio.create_task(
                self._bridge_events(relay, bridge),
                name="desktop-realtime-core-bridge",
            )

        async def sender() -> None:
            async for payload in relay.outgoing():
                await websocket.send_json(payload)

        sender_task = asyncio.create_task(sender(), name="desktop-realtime-renderer-sender")
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    message = json.loads(raw)
                except ValueError:
                    continue
                kind = message.get("kind")
                if kind == "desktop_latency":
                    turn = message.get("turn")
                    def metric(name: str) -> str:
                        value = message.get(name)
                        return "n/a" if value is None else f"{value} ms"
                    print(
                        "[Desktop latency] "
                        f"turn={turn} | "
                        f"speech_end->response_created={metric('speech_end_to_response_created_ms')} | "
                        f"speech_end->first_transcript={metric('speech_end_to_first_transcript_ms')} | "
                        f"speech_end->first_audio={metric('speech_end_to_first_audio_ms')} | "
                        f"response_created->first_audio={metric('response_created_to_first_audio_ms')}",
                        flush=True,
                    )
                    continue
                if kind != "realtime_event" or not isinstance(message.get("event"), dict):
                    continue
                await relay.feed_event(message["event"])
        except WebSocketDisconnect:
            pass
        finally:
            if not sender_task.done():
                sender_task.cancel()
            await asyncio.gather(sender_task, return_exceptions=True)
            await self.stop(expected_relay=relay)

    async def _bridge_events(self, relay: BrowserRealtimeRelay, bridge: RealtimeCoreBridge) -> None:
        async for event in relay.events():
            await bridge.handle_event(event)

    async def create_call(self, offer_sdp: str) -> tuple[str, str]:
        clean = str(offer_sdp or "").strip()
        if not clean:
            raise ValueError("WebRTC SDP offer is required")
        async with self._lock:
            relay = self._relay
            if relay is None:
                raise RuntimeError("desktop control channel must connect before WebRTC session creation")
            if relay.call_id is not None:
                raise RuntimeError("desktop Realtime call already exists")
        call_id, answer_sdp = await create_realtime_webrtc_call(self.config, clean)
        relay.set_call_id(call_id)
        return call_id, answer_sdp

    async def stop(self, *, expected_relay: BrowserRealtimeRelay | None = None) -> None:
        async with self._lock:
            relay = self._relay
            if relay is None:
                return
            if expected_relay is not None and relay is not expected_relay:
                return
            bridge = self._bridge
            event_task = self._event_task
            call_id = relay.call_id
            self._relay = None
            self._bridge = None
            self._event_task = None

        if call_id:
            with suppress(Exception):
                await hangup_realtime_call(self.config, call_id)
        if bridge is not None:
            with suppress(Exception):
                await bridge.close()
        with suppress(Exception):
            await relay.close()
        if event_task is not None and not event_task.done():
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(event_task, timeout=2.0)
            if not event_task.done():
                event_task.cancel()
        if event_task is not None:
            await asyncio.gather(event_task, return_exceptions=True)


def _missing_ui_page() -> str:
    return """<!doctype html><html><head><meta charset='utf-8'><title>Jarvis Desktop Alpha</title></head>
<body style='background:#070a10;color:#e7eefb;font-family:system-ui;padding:40px'>
<h1>Jarvis Desktop Alpha UI is not built.</h1>
<p>Run <code>npm install</code> once, then <code>npm run desktop:build</code>.</p>
</body></html>"""


def create_desktop_app(
    *,
    runtime: JarvisRuntime,
    provider: OpenAIProvider,
    realtime_config: OpenAIRealtimeConfig,
    static_dir: Path = DEFAULT_STATIC_DIR,
) -> FastAPI:
    version = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    session = DesktopRealtimeSession(runtime=runtime, config=realtime_config)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await session.stop()
            await provider.close()
            runtime.close()

    app = FastAPI(title="Jarvis Desktop Alpha Host", version=version, docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.jarvis_runtime = runtime
    app.state.desktop_realtime_session = session

    @app.get("/api/desktop/health")
    async def desktop_health() -> dict[str, Any]:
        snapshot = runtime.snapshot()
        return {
            "status": "ok",
            "version": version,
            "runtime_id": snapshot.runtime_id,
            "conversation_id": snapshot.conversation.conversation_id if snapshot.conversation else None,
            "realtime_active": session.active,
            "frontend": "openai-gpt-realtime",
            "model": realtime_config.model,
            "voice": realtime_config.voice,
            "transport": "webrtc",
        }

    @app.get("/api/desktop/config")
    async def desktop_config() -> dict[str, Any]:
        return {
            "version": version,
            "model": realtime_config.model,
            "voice": realtime_config.voice,
            "reasoning_effort": realtime_config.reasoning_effort,
            "transport": "webrtc",
        }

    @app.post("/api/realtime/session")
    async def create_realtime_session(body: dict[str, object]) -> dict[str, str]:
        try:
            call_id, answer_sdp = await session.create_call(str(body.get("sdp") or ""))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Realtime WebRTC creation failed: {type(exc).__name__}: {exc}") from exc
        return {"call_id": call_id, "sdp": answer_sdp}

    @app.post("/api/realtime/end")
    async def end_realtime_session() -> dict[str, bool]:
        await session.stop()
        return {"closed": True}

    @app.websocket("/ws/control")
    async def control_socket(websocket: WebSocket) -> None:
        await session.open_control(websocket)

    # Preserve the versioned Runtime API under a stable sub-path. The desktop
    # renderer does not need all of it yet, but future app features can grow on
    # this existing Core-owned contract instead of duplicating business logic.
    app.mount("/runtime", create_runtime_api(runtime))

    static_dir = Path(static_dir)
    index_path = static_dir / "index.html"
    if static_dir.exists() and index_path.exists():
        static_root = static_dir.resolve()

        @app.get("/", response_class=FileResponse)
        async def desktop_index() -> FileResponse:
            return FileResponse(index_path)

        @app.get("/{asset_path:path}")
        async def desktop_asset(asset_path: str) -> FileResponse:
            requested = (static_root / asset_path).resolve()
            if requested != static_root and static_root not in requested.parents:
                raise HTTPException(status_code=404, detail="desktop asset not found")
            if requested.is_file():
                return FileResponse(requested)
            # Electron is a single-page client. HTTP navigation falls back to
            # index.html, while websocket scopes never enter this GET-only route.
            return FileResponse(index_path)
    else:
        @app.get("/", response_class=HTMLResponse)
        async def missing_ui() -> HTMLResponse:
            return HTMLResponse(_missing_ui_page(), status_code=503)

    return app


def main() -> int:
    args = parser().parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("[FAIL] 0.1.0 Desktop Alpha host is loopback-only")
    if not 1024 <= args.port <= 65535:
        raise SystemExit("[FAIL] --port must be between 1024 and 65535")

    runtime, provider = build_runtime()
    realtime_config = OpenAIRealtimeConfig.from_env(env_file=PROJECT_ROOT / ".env")
    if not realtime_config.api_key:
        runtime.close()
        raise SystemExit("[FAIL] OPENAI_API_KEY is not configured in local .env")

    app = create_desktop_app(
        runtime=runtime,
        provider=provider,
        realtime_config=realtime_config,
        static_dir=args.static_dir,
    )
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
