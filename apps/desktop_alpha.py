"""Jarvis Core v2 0.1.1 desktop alpha host.

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
from core.voice import LocalWakeListener, WakeSleepConfig
from providers.stt.whisper_cpp import WhisperCppConfig, WhisperCppProvider
from providers.vad import WhisperCppSileroVadDetector
from providers.intelligence.openai import OpenAIProvider, OpenAIProviderConfig
from providers.voice_frontend.openai_realtime import (
    BrowserRealtimeRelay,
    OpenAIRealtimeConfig,
    RealtimeCoreBridge,
    create_realtime_webrtc_call,
    hangup_realtime_call,
)
from providers.voice_frontend.openai_realtime.webrtc import (
    DESKTOP_REALTIME_MAX_OUTPUT_TOKENS,
    NORMAL_RESPONSE_INSTRUCTIONS,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATIC_DIR = PROJECT_ROOT / "apps" / "desktop" / "dist"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Jarvis Core v2 0.1.1 Desktop Alpha host")
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


def _emit_presence(runtime: JarvisRuntime, target: str, reason: str) -> None:
    core = runtime.conversation
    if core is None:
        return
    snapshot = runtime.snapshot()
    previous = snapshot.conversation.presence_state if snapshot.conversation else None
    if previous == target:
        return
    runtime.event_bus.emit(
        "voice.presence.changed",
        origin="desktop-lifecycle",
        conversation_id=core.context.conversation_id,
        user_id=core.context.user_id,
        device_id=core.context.device_id,
        payload={"from": previous or "unknown", "to": target, "reason": reason},
    )


class DesktopWakeService:
    """Local-only sleeping listener fed by the Electron renderer microphone.

    The browser owns the physical microphone in every presence state. While
    sleeping it streams only 16 kHz PCM to this loopback service. Silero +
    Whisper remain local; OpenAI Realtime is not connected until a wake phrase
    is confirmed.
    """

    def __init__(self, *, runtime: JarvisRuntime, listener: LocalWakeListener) -> None:
        self.runtime = runtime
        self.listener = listener
        self._prepare_lock = asyncio.Lock()
        self._prepared = False

    async def prepare(self) -> None:
        if self._prepared:
            return
        async with self._prepare_lock:
            if self._prepared:
                return
            health = await self.listener.health()
            if not health.ready:
                raise RuntimeError(health.detail or f"wake STT is {health.status}")
            await self.listener.warmup()
            self._prepared = True

    async def listen(self, websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            await websocket.send_json({"kind": "wake_preparing"})
            await self.prepare()
            self.listener.reset()
            await websocket.send_json(
                {
                    "kind": "wake_ready",
                    "wake_phrases": list(self.listener.config.wake_phrases),
                    "idle_sleep_seconds": self.listener.config.idle_timeout_seconds,
                }
            )
            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    return
                payload = message.get("bytes")
                if payload is None:
                    continue
                result = await self.listener.feed_pcm(bytes(payload))
                if result is None:
                    continue
                if not result.woke or result.match is None:
                    await websocket.send_json({"kind": "wake_ignored"})
                    continue
                _emit_presence(self.runtime, "awake", "local_wake_phrase")
                await websocket.send_json(
                    {
                        "kind": "wake_detected",
                        "phrase": result.match.phrase,
                        "command_text": result.match.command_text,
                    }
                )
                return
        except WebSocketDisconnect:
            return
        except Exception as exc:
            with suppress(Exception):
                await websocket.send_json(
                    {"kind": "wake_unavailable", "detail": f"{type(exc).__name__}: {exc}"}
                )
        finally:
            self.listener.reset()
            with suppress(Exception):
                await websocket.close()

    async def close(self) -> None:
        await self.listener.close()


def build_wake_service(runtime: JarvisRuntime) -> DesktopWakeService:
    wake_config = WakeSleepConfig.from_env(env_file=PROJECT_ROOT / ".env")
    whisper_config = WhisperCppConfig.from_env(env_file=PROJECT_ROOT / ".env")
    # Sleeping wake detection waits for the local endpoint before transcription;
    # rolling partials would waste local inference without improving wake policy.
    whisper_config = replace(whisper_config, emit_partials=False)
    listener = LocalWakeListener(
        stt=WhisperCppProvider(whisper_config),
        vad=WhisperCppSileroVadDetector(),
        config=wake_config,
    )
    return DesktopWakeService(runtime=runtime, listener=listener)


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

        # Jarvis Core owns response policy. The renderer only forwards these
        # per-turn overrides when it manually creates a Realtime response.
        await websocket.send_json({
            "kind": "response_policy",
            "response": {
                "max_output_tokens": DESKTOP_REALTIME_MAX_OUTPUT_TOKENS,
                "instructions": NORMAL_RESPONSE_INSTRUCTIONS,
            },
        })

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
                event = message["event"]
                if str(event.get("type") or "") == "response.done" and isinstance(event.get("response"), dict):
                    response = event["response"]
                    details = response.get("status_details")
                    reason = None
                    if isinstance(details, dict):
                        reason = details.get("reason") or details.get("type")
                    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
                    output_details = usage.get("output_token_details") if isinstance(usage.get("output_token_details"), dict) else {}
                    print(
                        "[Desktop response budget] "
                        f"status={response.get('status')} | "
                        f"max_output_tokens={response.get('max_output_tokens')} | "
                        f"output_tokens={usage.get('output_tokens', 'n/a')} | "
                        f"text_tokens={output_details.get('text_tokens', 'n/a')} | "
                        f"audio_tokens={output_details.get('audio_tokens', 'n/a')} | "
                        f"reason={reason or 'natural'}",
                        flush=True,
                    )
                await relay.feed_event(event)
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
        call_id, answer_sdp = await create_realtime_webrtc_call(
            self.config,
            clean,
            auto_create_response=False,
            include_expand_response_tool=False,
        )
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
    wake_service: DesktopWakeService | None = None,
) -> FastAPI:
    version = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    session = DesktopRealtimeSession(runtime=runtime, config=realtime_config)
    wake_config = wake_service.listener.config if wake_service is not None else WakeSleepConfig.from_env(env_file=PROJECT_ROOT / ".env")
    _emit_presence(runtime, "sleeping", "desktop_start")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await session.stop()
            if wake_service is not None:
                await wake_service.close()
            await provider.close()
            runtime.close()

    app = FastAPI(title="Jarvis Desktop Alpha Host", version=version, docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.jarvis_runtime = runtime
    app.state.desktop_realtime_session = session
    app.state.desktop_wake_service = wake_service

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
            "presence": snapshot.conversation.presence_state if snapshot.conversation else None,
            "local_wake": wake_service is not None,
        }

    @app.get("/api/desktop/config")
    async def desktop_config() -> dict[str, Any]:
        return {
            "version": version,
            "model": realtime_config.model,
            "voice": realtime_config.voice,
            "reasoning_effort": realtime_config.reasoning_effort,
            "transport": "webrtc",
            "wake_phrases": list(wake_config.wake_phrases),
            "idle_sleep_seconds": wake_config.idle_timeout_seconds,
            "initial_presence": "sleeping",
            "local_wake": wake_service is not None,
        }

    @app.post("/api/presence/wake")
    async def presence_wake(body: dict[str, object] | None = None) -> dict[str, str]:
        reason = str((body or {}).get("reason") or "client_wake")
        _emit_presence(runtime, "awake", reason)
        return {"presence": "awake"}

    @app.post("/api/presence/sleep")
    async def presence_sleep(body: dict[str, object] | None = None) -> dict[str, str]:
        reason = str((body or {}).get("reason") or "client_sleep")
        await session.stop()
        _emit_presence(runtime, "sleeping", reason)
        return {"presence": "sleeping"}

    @app.websocket("/ws/wake")
    async def wake_socket(websocket: WebSocket) -> None:
        if wake_service is None:
            await websocket.accept()
            await websocket.send_json({"kind": "wake_unavailable", "detail": "local wake listener is not configured"})
            await websocket.close(code=1011)
            return
        await wake_service.listen(websocket)

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
        raise SystemExit("[FAIL] 0.1.1 Desktop Alpha host is loopback-only")
    if not 1024 <= args.port <= 65535:
        raise SystemExit("[FAIL] --port must be between 1024 and 65535")

    runtime, provider = build_runtime()
    realtime_config = OpenAIRealtimeConfig.from_env(env_file=PROJECT_ROOT / ".env")
    if not realtime_config.api_key:
        runtime.close()
        raise SystemExit("[FAIL] OPENAI_API_KEY is not configured in local .env")

    wake_service: DesktopWakeService | None = None
    try:
        wake_service = build_wake_service(runtime)
    except Exception as exc:
        # Keep the desktop usable for typed/manual wake if the local wake runtime
        # is not installed yet. Production packaging will ship this dependency.
        print(f"[WARN] Local wake listener unavailable: {type(exc).__name__}: {exc}", flush=True)

    app = create_desktop_app(
        runtime=runtime,
        provider=provider,
        realtime_config=realtime_config,
        static_dir=args.static_dir,
        wake_service=wake_service,
    )
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
