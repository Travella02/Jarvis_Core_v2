"""Jarvis 0.0.9 Repair4 OpenAI Realtime WebRTC A/B lab.

Realtime handles ordinary speech-to-speech conversation directly.  It receives
one narrow function for delegating private/current state, memory, actions,
background work, or stronger reasoning to authoritative Jarvis Core.  The
browser owns WebRTC audio; the project API key never enters the browser.
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import suppress
from dataclasses import replace
import json
from pathlib import Path
from time import monotonic
from typing import Any
import webbrowser

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.conversation.engine import VOICE_RESPONSE_INSTRUCTION
from core.intelligence import IntelligenceContext, IntelligenceEventType, ReasoningPolicy
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
WEB_PAGE = PROJECT_ROOT / "apps" / "web" / "gpt_realtime_webrtc_lab.html"
TEST_PHRASES = (
    "Jarvis, tell me something interesting about space.",
    "Why does that happen?",
    "Explain it more simply.",
    "Tell me another interesting fact.",
    "Tell me a short joke.",
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Jarvis 0.0.9 Repair4 OpenAI Realtime browser WebRTC A/B lab")
    result.add_argument("--turns", type=int, default=5)
    result.add_argument("--port", type=int, default=8766)
    result.add_argument("--voice", default=None, help="Realtime voice, e.g. cedar or marin")
    result.add_argument("--realtime-model", default=None, help="gpt-realtime-2.1 or gpt-realtime-2.1-mini")
    result.add_argument("--reasoning-effort", choices=("minimal", "low", "medium", "high", "xhigh"), default=None)
    result.add_argument("--luna-model", default=None)
    result.add_argument("--luna-service-tier", default=None)
    result.add_argument("--prewarm-core", action="store_true", help="opt in to a hidden backend warmup before listening")
    result.add_argument("--no-prewarm", action="store_true", help=argparse.SUPPRESS)
    result.add_argument("--no-browser", action="store_true")
    result.add_argument("--tail-seconds", type=float, default=5.0)
    result.add_argument("--max-seconds", type=float, default=240.0)
    return result


def _build_runtime(args: argparse.Namespace) -> tuple[JarvisRuntime, OpenAIProvider]:
    intelligence_config = OpenAIProviderConfig.from_env(env_file=PROJECT_ROOT / ".env")
    updates: dict[str, str] = {"voice_transport": "websocket"}
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
        speaker_id="gpt-realtime-webrtc-lab-user",
        device_id="gpt-realtime-webrtc-lab",
    )
    return runtime, luna


async def _prewarm_backend(provider: OpenAIProvider) -> None:
    started = monotonic()
    first_text_ms = None
    context = IntelligenceContext(
        trace=CorrelationContext.create(),
        messages=(
            {"role": "developer", "content": VOICE_RESPONSE_INSTRUCTION},
            {"role": "user", "content": "Reply with exactly one word: Ready."},
        ),
        metadata={"input_channel": "voice", "conversation_id": "gpt-realtime-webrtc-lab-prewarm"},
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
    print(f"Core backend warmup: {elapsed_ms:.0f} ms ({first_label}; output discarded).")


def _usage_from_response_done(payload: dict[str, Any]) -> tuple[int, int, int, int]:
    response = payload.get("response") if isinstance(payload.get("response"), dict) else {}
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    in_details = usage.get("input_token_details") if isinstance(usage.get("input_token_details"), dict) else {}
    out_details = usage.get("output_token_details") if isinstance(usage.get("output_token_details"), dict) else {}
    return (
        int(usage.get("input_tokens") or 0),
        int(usage.get("output_tokens") or 0),
        int(in_details.get("audio_tokens") or 0),
        int(out_details.get("audio_tokens") or 0),
    )


def _response_contains_function_call(payload: dict[str, Any]) -> bool:
    response = payload.get("response") if isinstance(payload.get("response"), dict) else {}
    output = response.get("output") if isinstance(response.get("output"), list) else []
    return any(isinstance(item, dict) and item.get("type") == "function_call" for item in output)


def build_app(
    *,
    realtime_config: OpenAIRealtimeConfig,
    relay: BrowserRealtimeRelay,
    version: str,
    disconnect_event: asyncio.Event,
) -> FastAPI:
    app = FastAPI(title="Jarvis OpenAI Realtime WebRTC Lab", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return HTMLResponse(WEB_PAGE.read_text(encoding="utf-8"))

    @app.get("/api/config")
    async def config() -> dict[str, object]:
        return {
            "version": version,
            "voice": realtime_config.voice,
            "model": realtime_config.model,
            "reasoning_effort": realtime_config.reasoning_effort,
            "phrases": list(TEST_PHRASES),
            "transport": "webrtc",
        }

    @app.post("/api/realtime/session")
    async def create_session(body: dict[str, object]) -> dict[str, str]:
        if relay.call_id is not None:
            raise HTTPException(status_code=409, detail="This lab already created a Realtime session")
        offer = str(body.get("sdp") or "")
        try:
            call_id, answer_sdp = await create_realtime_webrtc_call(realtime_config, offer)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Realtime WebRTC creation failed: {type(exc).__name__}: {exc}") from exc
        relay.set_call_id(call_id)
        print(f"OpenAI Realtime WebRTC call created: {call_id}")
        return {"call_id": call_id, "sdp": answer_sdp}

    @app.websocket("/ws/control")
    async def control_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        print("Browser Realtime control relay connected.")

        async def sender() -> None:
            async for payload in relay.outgoing():
                await websocket.send_json(payload)

        send_task = asyncio.create_task(sender(), name="realtime-webrtc-browser-sender")
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    message = json.loads(raw)
                except ValueError:
                    continue
                if message.get("kind") != "realtime_event" or not isinstance(message.get("event"), dict):
                    continue
                await relay.feed_event(message["event"])
        except WebSocketDisconnect:
            pass
        finally:
            if not send_task.done():
                send_task.cancel()
            await asyncio.gather(send_task, return_exceptions=True)
            disconnect_event.set()
            print("Browser Realtime control relay disconnected.")

    return app


async def run(args: argparse.Namespace) -> int:
    if args.turns <= 0:
        raise ValueError("--turns must be positive")
    if not 1024 <= args.port <= 65535:
        raise ValueError("--port must be between 1024 and 65535")

    runtime, luna = _build_runtime(args)
    conversation = runtime.conversation
    assert conversation is not None

    realtime_config = OpenAIRealtimeConfig.from_env(env_file=PROJECT_ROOT / ".env")
    updates = {}
    if args.voice:
        updates["voice"] = args.voice
    if args.realtime_model:
        updates["model"] = args.realtime_model
    if args.reasoning_effort:
        updates["reasoning_effort"] = args.reasoning_effort
    if updates:
        realtime_config = replace(realtime_config, **updates)
    if not realtime_config.api_key:
        await luna.close()
        runtime.close()
        raise RuntimeError("OPENAI_API_KEY is not configured")

    if args.prewarm_core and not args.no_prewarm:
        await _prewarm_backend(luna)

    relay = BrowserRealtimeRelay()
    bridge = RealtimeCoreBridge(conversation=conversation, relay=relay)
    disconnect_event = asyncio.Event()
    completion_event = asyncio.Event()
    response_count = 0
    user_turn_count = 0
    delegated_count = 0
    input_tokens = output_tokens = input_audio_tokens = output_audio_tokens = 0
    caption_speaker: str | None = None

    async def event_loop() -> None:
        nonlocal response_count, user_turn_count, delegated_count, input_tokens, output_tokens, input_audio_tokens, output_audio_tokens, caption_speaker
        async for event in relay.events():
            event_type = str(event.get("type") or "")
            if event_type == "input_audio_buffer.speech_stopped":
                user_turn_count += 1
                print(f"\n[User turn {user_turn_count}/{args.turns} captured]", flush=True)
            elif event_type == "response.output_audio_transcript.delta":
                if caption_speaker != "assistant":
                    print("\nJarvis: ", end="", flush=True)
                    caption_speaker = "assistant"
                print(str(event.get("delta") or ""), end="", flush=True)
            elif event_type == "response.function_call_arguments.done":
                delegated_count += 1
                print(f"\n[Realtime delegated to Jarvis Core: {event.get('call_id') or '?'}]", flush=True)
            elif event_type == "response.done":
                response_count += 1
                it, ot, ia, oa = _usage_from_response_done(event)
                input_tokens += it
                output_tokens += ot
                input_audio_tokens += ia
                output_audio_tokens += oa
                status = (event.get("response") or {}).get("status") if isinstance(event.get("response"), dict) else None
                print(f"\n[Realtime response {response_count}: {status or 'done'}]", flush=True)
                if (
                    user_turn_count >= args.turns
                    and status == "completed"
                    and not _response_contains_function_call(event)
                    and bridge.pending_count == 0
                ):
                    completion_event.set()
            elif event_type == "error":
                error = event.get("error") if isinstance(event.get("error"), dict) else {}
                print(f"\n[Realtime error] {error.get('message') or 'unknown error'}", flush=True)
            await bridge.handle_event(event)

    version = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    app = build_app(
        realtime_config=realtime_config,
        relay=relay,
        version=version,
        disconnect_event=disconnect_event,
    )
    config = uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    server_task = asyncio.create_task(server.serve(), name="gpt-realtime-webrtc-local-server")
    for _ in range(100):
        if server.started:
            break
        if server_task.done():
            await server_task
        await asyncio.sleep(0.05)
    if not server.started:
        raise RuntimeError("Local Realtime WebRTC lab server did not start")

    url = f"http://127.0.0.1:{args.port}/"
    print("Jarvis Core v2 0.0.9 Repair6 Realtime Mini + Core Delegation Acceptance Lab")
    print(f"Voice: {realtime_config.voice} | Realtime model: {realtime_config.model} | reasoning={realtime_config.reasoning_effort}")
    print(f"Core test route: {luna.metadata.model} (selected behind Jarvis Core; conversational frontend does not own backend routing)")
    print("Media: browser WebRTC | simple conversation stays in Realtime Mini | delegated work enters authoritative Core")
    print(f"Open: {url}")
    print("Say these exact phrases:")
    for index, phrase in enumerate(TEST_PHRASES, start=1):
        print(f"  {index}. {phrase}")
    print("  For #4, start speaking before Jarvis finishes #3.")
    if not args.no_browser:
        webbrowser.open(url)

    events_task = asyncio.create_task(event_loop(), name="gpt-realtime-webrtc-events")
    completion_wait_task = asyncio.create_task(completion_event.wait(), name="gpt-realtime-webrtc-completion")
    disconnect_wait_task = asyncio.create_task(disconnect_event.wait(), name="gpt-realtime-webrtc-disconnect")
    timeout_task = asyncio.create_task(asyncio.sleep(args.max_seconds), name="gpt-realtime-webrtc-timeout")
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
            print("\n[Browser control connection closed]")
    finally:
        # Close Core work first, then explicitly tear down both browser media and
        # the server-side Realtime call. This prevents an orphaned billable voice
        # session if the terminal exits before the browser UI is closed manually.
        await bridge.close()
        await relay.request_browser_close()
        with suppress(Exception):
            await hangup_realtime_call(realtime_config, relay.call_id)
        await relay.close()
        for task in (events_task, completion_wait_task, disconnect_wait_task, timeout_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(events_task, completion_wait_task, disconnect_wait_task, timeout_task, return_exceptions=True)
        server.should_exit = True
        with suppress(Exception):
            await asyncio.wait_for(server_task, timeout=3.0)
        await luna.close()
        runtime.close()

    print(f"User turns observed: {user_turn_count}")
    print(f"Realtime responses observed: {response_count}")
    print(f"Jarvis Core delegations observed: {delegated_count}")
    print(f"Realtime usage tokens: input={input_tokens}, output={output_tokens}, audio_in={input_audio_tokens}, audio_out={output_audio_tokens}")
    accepted = user_turn_count >= args.turns and completion_event.is_set()
    print("Status: ok" if accepted else "Status: incomplete")
    return 0 if accepted else 1


def main() -> int:
    args = parser().parse_args()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\nRealtime WebRTC lab interrupted by user; browser/call teardown requested.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
