"""Jarvis 0.0.9 Repair2 browser WebRTC A/B lab.

The browser owns real-time media. Python remains the trusted Jarvis Core and
OpenAI session broker. GPT-Live JSON events are relayed over localhost only;
client delegation still enters the existing Conversation Core/Luna path.
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import suppress
from dataclasses import replace
import json
from pathlib import Path
from time import monotonic
import webbrowser

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.conversation.engine import VOICE_RESPONSE_INSTRUCTION
from core.intelligence import IntelligenceContext, IntelligenceEventType, ReasoningPolicy
from core.runtime import IntelligenceProviderRouter, JarvisRuntime, RuntimeSettings
from core.voice.frontend import VoiceFrontendEventType, VoiceFrontendSessionConfig
from core.voice.live_bridge import LiveConversationBridge
from providers.intelligence.openai import OpenAIProvider, OpenAIProviderConfig
from providers.voice_frontend.openai_live import OpenAIGPTLiveConfig
from providers.voice_frontend.openai_live.provider import LIVE_CONVERSATION_INSTRUCTIONS
from providers.voice_frontend.openai_live.webrtc import BrowserWebRTCRelaySession, create_webrtc_session


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_PAGE = PROJECT_ROOT / "apps" / "web" / "gpt_live_webrtc_lab.html"
TEST_PHRASES = (
    "Jarvis, tell me something interesting about space.",
    "Why does that happen?",
    "Explain it more simply.",
    "Tell me another interesting fact.",
    "Tell me a short joke.",
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Jarvis 0.0.9 Repair2 GPT-Live browser WebRTC lab")
    result.add_argument("--turns", type=int, default=5)
    result.add_argument("--port", type=int, default=8765)
    result.add_argument("--voice", default=None)
    result.add_argument("--live-model", default=None)
    result.add_argument("--luna-model", default=None)
    result.add_argument("--luna-service-tier", default=None)
    result.add_argument("--no-prewarm", action="store_true")
    result.add_argument("--no-browser", action="store_true", help="Do not automatically open the local WebRTC page")
    result.add_argument("--tail-seconds", type=float, default=3.0)
    result.add_argument("--max-seconds", type=float, default=240.0)
    return result


def _build_runtime(args: argparse.Namespace) -> tuple[JarvisRuntime, OpenAIProvider]:
    intelligence_config = OpenAIProviderConfig.from_env(env_file=PROJECT_ROOT / ".env")
    updates = {"voice_transport": "websocket"}
    if args.luna_model:
        updates["model"] = args.luna_model
    if args.luna_service_tier:
        updates["service_tier"] = args.luna_service_tier
    intelligence_config = replace(intelligence_config, **updates)
    luna = OpenAIProvider(intelligence_config)
    runtime_settings = RuntimeSettings.from_env(env_file=PROJECT_ROOT / ".env")
    router = IntelligenceProviderRouter(default_route=runtime_settings.default_intelligence_route)
    router.register(runtime_settings.default_intelligence_route, luna, make_default=True)
    runtime = JarvisRuntime(settings=runtime_settings, provider_router=router)
    runtime.start()
    runtime.create_conversation(
        user_id="local-development-user",
        speaker_id="gpt-live-webrtc-lab-user",
        device_id="gpt-live-webrtc-lab",
    )
    return runtime, luna


async def _prewarm_luna(provider: OpenAIProvider) -> None:
    started = monotonic()
    first_text_ms = None
    context = IntelligenceContext(
        trace=CorrelationContext.create(),
        messages=(
            {"role": "developer", "content": VOICE_RESPONSE_INSTRUCTION},
            {"role": "user", "content": "Reply with exactly one word: Ready."},
        ),
        metadata={"input_channel": "voice", "conversation_id": "gpt-live-webrtc-lab-prewarm"},
    )
    async for event in provider.stream_response(
        context,
        (),
        ReasoningPolicy(level="none", allow_escalation=False),
        CancellationToken(),
    ):
        if event.event_type is IntelligenceEventType.TEXT_DELTA and first_text_ms is None:
            first_text_ms = (monotonic() - started) * 1000.0
    elapsed_ms = (monotonic() - started) * 1000.0
    first_label = f"{first_text_ms:.0f} ms TTFT" if first_text_ms is not None else "no text delta"
    print(f"Luna warmup: {elapsed_ms:.0f} ms ({first_label}; output discarded).")


def build_app(
    *,
    live_config: OpenAIGPTLiveConfig,
    session_config: VoiceFrontendSessionConfig,
    relay: BrowserWebRTCRelaySession,
    bridge: LiveConversationBridge,
    version: str,
    completion_event: asyncio.Event,
    disconnect_event: asyncio.Event,
) -> FastAPI:
    app = FastAPI(title="Jarvis GPT-Live WebRTC Lab", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return HTMLResponse(WEB_PAGE.read_text(encoding="utf-8"))

    @app.get("/api/config")
    async def config() -> dict[str, object]:
        return {
            "version": version,
            "voice": session_config.voice,
            "model": live_config.model,
            "phrases": list(TEST_PHRASES),
            "transport": "webrtc",
        }

    @app.post("/api/live/session")
    async def create_session(body: dict[str, object]) -> dict[str, str]:
        if relay.session_id is not None:
            raise HTTPException(status_code=409, detail="This lab already created a GPT-Live session")
        offer = str(body.get("sdp") or "")
        try:
            session_id, answer_sdp = await create_webrtc_session(live_config, session_config, offer)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"GPT-Live WebRTC creation failed: {type(exc).__name__}: {exc}") from exc
        relay.set_session_id(session_id)
        print(f"GPT-Live WebRTC session created: {session_id}")
        return {"session_id": session_id, "sdp": answer_sdp}

    @app.websocket("/ws/control")
    async def control_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        print("Browser WebRTC control relay connected.")

        async def sender() -> None:
            async for payload in relay.outgoing():
                await websocket.send_json(payload)

        send_task = asyncio.create_task(sender(), name="gpt-live-webrtc-browser-sender")
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    message = json.loads(raw)
                except ValueError:
                    continue
                if message.get("kind") != "live_event" or not isinstance(message.get("event"), dict):
                    continue
                await relay.feed_live_event(message["event"])
        except WebSocketDisconnect:
            pass
        finally:
            if not send_task.done():
                send_task.cancel()
            await asyncio.gather(send_task, return_exceptions=True)
            disconnect_event.set()
            print("Browser WebRTC control relay disconnected.")

    return app


async def run(args: argparse.Namespace) -> int:
    if args.turns <= 0:
        raise ValueError("--turns must be positive")
    if not 1024 <= args.port <= 65535:
        raise ValueError("--port must be between 1024 and 65535")

    runtime, luna = _build_runtime(args)
    conversation = runtime.conversation
    assert conversation is not None

    live_config = OpenAIGPTLiveConfig.from_env(env_file=PROJECT_ROOT / ".env")
    if args.voice:
        live_config = replace(live_config, voice=args.voice)
    if args.live_model:
        live_config = replace(live_config, model=args.live_model)
    if not live_config.api_key:
        await luna.close()
        runtime.close()
        raise RuntimeError("OPENAI_API_KEY is not configured")

    if not args.no_prewarm:
        await _prewarm_luna(luna)

    session_config = VoiceFrontendSessionConfig(
        instructions=LIVE_CONVERSATION_INSTRUCTIONS,
        voice=live_config.voice,
        # Ignored by WebRTC media negotiation but retained in the provider-neutral contract.
        sample_rate_hz=live_config.audio_rate_hz,
        history=(),
        store=False,
    )
    relay = BrowserWebRTCRelaySession()
    bridge = LiveConversationBridge(conversation=conversation, session=relay)
    completion_event = asyncio.Event()
    disconnect_event = asyncio.Event()
    completed_turns = 0
    latest_usage_seconds = 0.0
    caption_speaker: str | None = None

    def on_backend_completed(event) -> None:
        nonlocal completed_turns
        completed_turns += 1
        backend_ms = event.payload.get("backend_ms", "?")
        print(f"\n[Jarvis Core backend complete: {backend_ms} ms | delegated turn {completed_turns}/{args.turns}]")
        if completed_turns >= args.turns:
            completion_event.set()

    unsubscribe = runtime.event_bus.subscribe("voice.frontend.delegation.completed", on_backend_completed)

    async def event_loop() -> None:
        nonlocal latest_usage_seconds, caption_speaker
        async for event in relay.events():
            if event.event_type is VoiceFrontendEventType.INPUT_TRANSCRIPT_DELTA:
                if caption_speaker != "user":
                    print("\nYou: ", end="", flush=True)
                    caption_speaker = "user"
                print(event.text, end="", flush=True)
            elif event.event_type is VoiceFrontendEventType.OUTPUT_TRANSCRIPT_DELTA:
                if caption_speaker != "assistant":
                    print("\nJarvis: ", end="", flush=True)
                    caption_speaker = "assistant"
                print(event.text, end="", flush=True)
            elif event.event_type is VoiceFrontendEventType.DELEGATION_REQUESTED:
                print(f"\n[GPT-Live delegated to Jarvis Core: {event.delegation_id or '?'}]", flush=True)
            elif event.event_type is VoiceFrontendEventType.USAGE_UPDATED:
                latest_usage_seconds = max(latest_usage_seconds, float(event.usage_seconds or 0.0))
            elif event.event_type is VoiceFrontendEventType.ERROR:
                print(f"\n[GPT-Live error] {event.detail or 'unknown error'}", flush=True)
            await bridge.handle_event(event)

    version = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    app = build_app(
        live_config=live_config,
        session_config=session_config,
        relay=relay,
        bridge=bridge,
        version=version,
        completion_event=completion_event,
        disconnect_event=disconnect_event,
    )
    config = uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    server_task = asyncio.create_task(server.serve(), name="gpt-live-webrtc-local-server")
    for _ in range(100):
        if server.started:
            break
        if server_task.done():
            await server_task
        await asyncio.sleep(0.05)
    if not server.started:
        raise RuntimeError("Local WebRTC lab server did not start")

    url = f"http://127.0.0.1:{args.port}/"
    print("Jarvis Core v2 0.0.9 Repair2 GPT-Live WebRTC Lab")
    print(f"Voice: {live_config.voice} | Live model: {live_config.model} | Backend: {luna.metadata.model}")
    print("Media: browser WebRTC (no Python PCM resampling or sounddevice output path)")
    print("Control: localhost browser relay -> authoritative Jarvis Core/Luna client delegation")
    print(f"Open: {url}")
    print("Browser actions: click 'Enable audio devices', select HyperX mic/headphones, then click 'Start GPT-Live test'.")
    print("Say these exact phrases:")
    for index, phrase in enumerate(TEST_PHRASES, start=1):
        print(f"  {index}. {phrase}")
    print("  For #4, start speaking before Jarvis finishes #3.")
    if not args.no_browser:
        webbrowser.open(url)

    events_task = asyncio.create_task(event_loop(), name="gpt-live-webrtc-events")
    completion_wait_task = asyncio.create_task(completion_event.wait(), name="gpt-live-webrtc-completion")
    disconnect_wait_task = asyncio.create_task(disconnect_event.wait(), name="gpt-live-webrtc-disconnect")
    timeout_task = asyncio.create_task(asyncio.sleep(args.max_seconds), name="gpt-live-webrtc-timeout")
    try:
        done, _ = await asyncio.wait(
            {completion_wait_task, disconnect_wait_task, timeout_task, events_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if completion_event.is_set():
            if args.tail_seconds:
                await asyncio.sleep(args.tail_seconds)
            await relay.request_browser_close()
            await asyncio.sleep(0.25)
        elif timeout_task in done:
            print(f"\n[Lab safety timeout after {args.max_seconds:.1f}s]")
        elif disconnect_wait_task in done:
            print("\n[Browser control connection closed before acceptance completed]")
    finally:
        await bridge.close()
        await relay.request_browser_close()
        await relay.close()
        for task in (events_task, completion_wait_task, disconnect_wait_task, timeout_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(events_task, completion_wait_task, disconnect_wait_task, timeout_task, return_exceptions=True)
        server.should_exit = True
        with suppress(Exception):
            await asyncio.wait_for(server_task, timeout=3.0)
        unsubscribe()
        await luna.close()
        runtime.close()

    print(f"Final GPT-Live usage observed: {latest_usage_seconds:.1f} seconds")
    print(f"Delegated backend turns completed: {completed_turns}")
    print("Status: ok" if completed_turns >= args.turns else "Status: incomplete")
    return 0 if completed_turns >= args.turns else 1


def main() -> int:
    args = parser().parse_args()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\nGPT-Live WebRTC lab interrupted by user.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
