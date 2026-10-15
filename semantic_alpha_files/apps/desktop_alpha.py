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
import sys
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
import uvicorn

from apps.runtime_api import create_app as create_runtime_api
from apps.desktop_luna import DesktopLunaDelegator
from core.intelligence import DelegationOrchestrator
from apps.desktop_actions import DesktopActionSession
from apps.desktop_semantic_actions import SemanticDesktopActionSession
from core.runtime import IntelligenceProviderRouter, JarvisRuntime, RuntimeSettings
from core.voice import LocalWakeListener, WakeSleepConfig
from providers.stt.whisper_cpp import WhisperCppConfig, WhisperCppProvider
from providers.vad import WhisperCppSileroVadDetector
from providers.intelligence.openai import OpenAIProvider, OpenAIProviderConfig
from providers.intelligence.openai.decisions_shadow import DecisionsShadowProbe
from providers.intelligence.openai.config import merged_environment
from providers.voice_frontend.openai_realtime import (
    BrowserRealtimeRelay,
    OpenAIRealtimeConfig,
    RealtimeCoreBridge,
    create_realtime_webrtc_call,
    hangup_realtime_call,
)
from providers.voice_frontend.openai_realtime.parallel_probe import ParallelShadowProbe
from providers.voice_frontend.openai_realtime.bench import RealtimeBenchmark
from providers.voice_frontend.openai_realtime.tool_probe import probe_response_policy, overlap_probe_response_policy, ALLOWED_PROBE_TOOLS
from providers.voice_frontend.openai_realtime.webrtc import (
    ROUTER_REALTIME_MAX_OUTPUT_TOKENS,
    ROUTER_REALTIME_REASONING_EFFORT,
    ROUTE_TURN_TOOL,
    ROUTE_TURN_TOOL_NAME,
    TURN_ROUTER_INSTRUCTIONS,
    DIRECT_ONLY_BENCHMARK_INSTRUCTIONS,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATIC_DIR = PROJECT_ROOT / "apps" / "desktop" / "dist"


def _terminal_chat_text(value: object, *, limit: int = 8000) -> str:
    """Safely print user/assistant text in Windows terminals with legacy encodings.

    This affects only the *debug representation*, never the actual transcript
    passed to Core or Realtime. Modern UTF-8 consoles retain readable Unicode;
    legacy Windows cp1252 consoles see JSON escapes for unsupported glyphs.
    """
    clean = " ".join(str(value or "").replace("\x1b", "").split())
    if len(clean) > limit:
        clean = clean[: max(0, limit - 1)] + "…"
    rendered = json.dumps(clean, ensure_ascii=False)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        rendered.encode(encoding)
    except (UnicodeError, LookupError):
        return json.dumps(clean, ensure_ascii=True)
    return rendered


def _configure_terminal_output() -> None:
    """A logging failure must never disconnect Jarvis's control WebSocket.

    The host shares stdout/stderr with npm on Windows; cp1252 often cannot
    represent transcripts, provider error text or exceptions. Keep the active
    encoding, but escape otherwise unencodable glyphs in *all* log messages.
    Do not change voice, provider requests, transcripts, or runtime settings.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(errors="backslashreplace")
        except (OSError, ValueError, TypeError):
            # Embedded or captured streams may not support reconfiguration.
            pass


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Jarvis Core v2 0.1.1 Desktop Alpha host")
    result.add_argument("--host", default="127.0.0.1")
    result.add_argument("--port", type=int, default=8765)
    result.add_argument("--static-dir", type=Path, default=DEFAULT_STATIC_DIR)
    return result


def _desktop_core_luna_budget(
    config: OpenAIProviderConfig, env: dict[str, str]
) -> OpenAIProviderConfig:
    """Use >=1024 tokens for desktop Luna, even with a legacy 256 .env.

    The dedicated desktop-only override permits intentional A/B comparisons.
    An existing higher general voice budget stays respected.
    """
    raw = env.get("JARVIS_DESKTOP_LUNA_VOICE_MAX_OUTPUT_TOKENS")
    if raw is None:
        limit = max(1024, config.voice_max_output_tokens)
    else:
        limit = int(raw)
    if not 128 <= limit <= 8192:
        raise ValueError("JARVIS_DESKTOP_LUNA_VOICE_MAX_OUTPUT_TOKENS must be 128..8192")
    return replace(config, voice_max_output_tokens=limit)


def build_runtime() -> tuple[JarvisRuntime, OpenAIProvider, tuple[OpenAIProvider, ...], DelegationOrchestrator]:
    intelligence_config = _desktop_core_luna_budget(
        OpenAIProviderConfig.from_env(env_file=PROJECT_ROOT / ".env"),
        merged_environment(PROJECT_ROOT / ".env"),
    )
    # Keep backend intelligence independent from the client-facing WebRTC
    # transport. The conversational frontend asks Core for a goal; this
    # composition root registers replaceable backend routes behind Core.
    intelligence_config = replace(intelligence_config, voice_transport="websocket")
    provider = OpenAIProvider(intelligence_config)
    providers: list[OpenAIProvider] = [provider]
    runtime_settings = RuntimeSettings.from_env(env_file=PROJECT_ROOT / ".env")
    router = IntelligenceProviderRouter(default_route=runtime_settings.default_intelligence_route)
    router.register(runtime_settings.default_intelligence_route, provider, make_default=True)

    env = merged_environment(PROJECT_ROOT / ".env")
    strong_model = str(env.get("JARVIS_OPENAI_STRONG_MODEL") or "").strip()
    strong_reasoning = str(env.get("JARVIS_OPENAI_STRONG_REASONING_EFFORT") or "low").strip().lower() or "low"
    if strong_reasoning not in {"none", "low", "medium", "high", "xhigh", "max"}:
        raise ValueError(f"Unsupported JARVIS_OPENAI_STRONG_REASONING_EFFORT={strong_reasoning!r}")
    if strong_model and strong_model != intelligence_config.model:
        strong_provider = OpenAIProvider(
            replace(
                intelligence_config,
                model=strong_model,
                reasoning_effort=strong_reasoning,
            )
        )
        router.register("strong", strong_provider)
        providers.append(strong_provider)

    runtime = JarvisRuntime(settings=runtime_settings, provider_router=router)
    runtime.start()
    runtime.create_conversation(
        user_id="local-development-user",
        speaker_id="desktop-alpha-user",
        device_id="desktop-alpha",
    )
    orchestrator = DelegationOrchestrator(
        provider_router=router,
        default_route=runtime_settings.default_intelligence_route,
        strong_route="strong",
        strong_reasoning_level=strong_reasoning,
    )
    return runtime, provider, tuple(providers), orchestrator


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
        # Wake utterances remain local. Show their transcript only when the
        # existing development conversation trace is explicitly enabled.
        env = merged_environment(PROJECT_ROOT / ".env")
        self.trace_enabled = str(env.get("JARVIS_DESKTOP_CONVERSATION_TRACE", "0")).lower() in {"1", "true", "yes", "on"}
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
            print("[Jarvis Wake] phase=preparing | engine=local_whisper_silero", flush=True)
            await websocket.send_json({"kind": "wake_preparing"})
            await self.prepare()
            self.listener.reset()
            print("[Jarvis Wake] phase=ready | waiting_for=audio_tap", flush=True)
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
                    # Renderer acknowledgement proves that microphone capture
                    # has actually started, rather than just socket readiness.
                    raw = message.get("text")
                    if raw:
                        try:
                            control = json.loads(raw)
                        except (ValueError, TypeError):
                            control = {}
                        if control.get("kind") == "wake_audio_tap_ready":
                            print("[Jarvis Wake] phase=listening | microphone=active", flush=True)
                        elif control.get("kind") == "wake_audio_tap_error":
                            detail = _terminal_chat_text(control.get("detail", "unknown"), limit=180)
                            print(f"[Jarvis Wake] phase=mic_error | detail={detail}", flush=True)
                    continue
                result = await self.listener.feed_pcm(bytes(payload))
                if result is None:
                    continue
                if not result.woke or result.match is None:
                    if self.trace_enabled:
                        print(
                            f"[Jarvis Wake] phase=ignored | transcript={_terminal_chat_text(result.transcript, limit=250)}",
                            flush=True,
                        )
                    else:
                        print("[Jarvis Wake] phase=ignored | transcript=hidden", flush=True)
                    await websocket.send_json({"kind": "wake_ignored"})
                    continue
                print(
                    f"[Jarvis Wake] phase=detected | phrase={_terminal_chat_text(result.match.phrase, limit=80)} "
                    f"| command_present={bool(result.match.command_text)}",
                    flush=True,
                )
                _emit_presence(self.runtime, "awake", "local_wake_phrase")
                await websocket.send_json(
                    {
                        "kind": "wake_detected",
                        "phrase": result.match.phrase,
                        "command_text": result.match.command_text,
                        # Only a confirmed wake with no attached command becomes an
                        # acknowledgment turn. The exact locally verified phrase
                        # is forwarded; wake-plus-command behavior is unchanged.
                        "wake_only_transcript": result.transcript if not result.match.command_text else "",
                    }
                )
                return
        except WebSocketDisconnect:
            return
        except Exception as exc:
            print(f"[Jarvis Wake] phase=unavailable | error={type(exc).__name__} "
                  f"| detail={_terminal_chat_text(str(exc), limit=250)}", flush=True)
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

    def __init__(
        self,
        *,
        runtime: JarvisRuntime,
        config: OpenAIRealtimeConfig,
        delegation_orchestrator: DelegationOrchestrator | None = None,
    ) -> None:
        if runtime.conversation is None:
            raise RuntimeError("JarvisRuntime conversation must exist before desktop voice starts")
        self.runtime = runtime
        self.config = config
        self.delegation_orchestrator = delegation_orchestrator
        self._relay: BrowserRealtimeRelay | None = None
        self._bridge: RealtimeCoreBridge | None = None
        self._event_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._parallel_probe: ParallelShadowProbe | None = None
        self._decisions_shadow: DecisionsShadowProbe | None = None
        self._luna: DesktopLunaDelegator | None = None
        self._bench = RealtimeBenchmark(config.model)
        env = merged_environment(PROJECT_ROOT / '.env')
        self._actions_enabled = (config.overlap_probe and config.core_luna_probe and
            str(env.get('JARVIS_CORE_ACTIONS_PROBE','0')).lower() in {'1','true','yes','on'})
        self._semantic_actions = self._actions_enabled and str(env.get('JARVIS_SEMANTIC_ACTIONS_PROBE','0')).lower() in {'1','true','yes','on'}
        self._action_session = (SemanticDesktopActionSession() if self._semantic_actions else DesktopActionSession()) if self._actions_enabled else None

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
            bridge = RealtimeCoreBridge(
                conversation=self.runtime.conversation,
                relay=relay,
                delegation_orchestrator=self.delegation_orchestrator,
            )
            self._relay = relay
            self._bridge = bridge
            if self._actions_enabled:
                self._action_session = SemanticDesktopActionSession() if self._semantic_actions else DesktopActionSession()
            if self.config.core_luna_probe:
                if not self.config.overlap_probe or self.delegation_orchestrator is None:
                    raise RuntimeError("Core Luna mode requires overlap and Core delegation orchestration")
                self._luna = DesktopLunaDelegator(
                    orchestrator=self.delegation_orchestrator,
                    conversation=self.runtime.conversation,
                    notify=relay.notify_desktop,
                    result_hold_seconds=self.config.luna_result_hold_seconds,
                )
                print(f"[Jarvis Luna] mode=real_core_reasoning | actions={'approved_site_only' if self._actions_enabled else 'dry_run'} | audio=private_pcm | authority=core", flush=True)
            if self.config.decisions_shadow_probe:
                if not self.config.overlap_probe or not self.config.api_key:
                    raise RuntimeError("Decisions shadow requires mini-overlap and a backend OpenAI key")
                self._decisions_shadow = DecisionsShadowProbe(self.config.api_key)
                print("[Jarvis Decisions Shadow] mode=read_only | billing=extra_input_tokens "
                      f"| transcript=dev_only | audio=unchanged | routing=mini | "
                      f"core_luna={'on' if self.config.core_luna_probe else 'off'}", flush=True)
            if self.config.parallel_shadow_probe and not self.config.direct_only_benchmark:
                provider = self.runtime.provider_router.resolve()
                if not isinstance(provider, OpenAIProvider):
                    raise RuntimeError("Parallel shadow requires an OpenAI intelligence provider for this prototype")
                # Isolate speculative inference from the authoritative provider's
                # stateful voice WebSocket, conversation, and tool permissions.
                shadow_config = replace(provider.config, voice_transport="http", max_output_tokens=96, store_responses=False)
                self._parallel_probe = ParallelShadowProbe(OpenAIProvider(shadow_config))
            self._event_task = asyncio.create_task(
                self._bridge_events(relay, bridge),
                name="desktop-realtime-core-bridge",
            )

        # The standard safe router is unchanged. The opt-in fast A/B mode
        # removes routing only when all tools are blocked for the entire turn.
        direct_only = self.config.direct_only_benchmark
        tool_probe = self.config.tool_selection_probe
        buffered_probe = self.config.buffered_tool_probe
        overlap_probe = self.config.overlap_probe
        if self.config.delegation_guidance_probe and not (self.config.core_luna_probe and overlap_probe):
            raise RuntimeError("0.1.4.1 guidance requires real Core/Luna overlap mode")
        direct_only = direct_only and not (tool_probe or buffered_probe or overlap_probe)
        policy = (overlap_probe_response_policy() if overlap_probe else probe_response_policy() if tool_probe else {
            **probe_response_policy(),
            "output_modalities": ["audio"],
            "max_output_tokens": 512,
            "instructions": "You are Jarvis in an experimental audio tool-selection session. Basic conversation: respond directly. For deep architecture/coding reasoning call ask_luna; for external actions call test_action. These are DRY RUN tools and cannot actually execute. Do not say any action was completed. Do not announce a tool before selecting it. Your audio is held privately until the entire response is evaluated. If a tool result says not executed, say so clearly.",
            "metadata": {"jarvis_stage": "buffered_tool_probe"},
        } if buffered_probe else {
            "max_output_tokens": 1024,
            "instructions": DIRECT_ONLY_BENCHMARK_INSTRUCTIONS,
            "output_modalities": ["audio"],
            "tools": [],
            "tool_choice": "none",
            "metadata": {"jarvis_stage": "direct_no_gate"},
        } if direct_only else {
            "max_output_tokens": ROUTER_REALTIME_MAX_OUTPUT_TOKENS,
            "instructions": TURN_ROUTER_INSTRUCTIONS,
            "output_modalities": ["text"],
            "reasoning": {"effort": ROUTER_REALTIME_REASONING_EFFORT},
            "tools": [ROUTE_TURN_TOOL],
            "tool_choice": {"type": "function", "name": ROUTE_TURN_TOOL_NAME},
            "metadata": {"jarvis_stage": "route"},
        })
        if self.config.core_luna_probe:
            # Only this opt-in mode changes the probe policy. Core still owns
            # provider choice, and external actions remain in dry-run mode.
            policy = json.loads(json.dumps(policy))
            for tool in policy.get("tools", []):
                if tool.get("name") == "ask_luna":
                    tool["description"] = "Request real, Core-authorized backend reasoning for complex analysis, software design, or coding. The tool selects reasoning only; no computer actions or background tasks are executed."
            policy["instructions"] = str(policy.get("instructions", "")).replace(
                "For complex coding/architecture/analysis use ask_luna (dry run).",
                "For complex coding/architecture/analysis use ask_luna, which invokes Core's real intelligence provider.",
            ).replace(
                "Never claim that Luna or an action ran. No real external tools execute in this experiment.",
                "Do not claim external actions were completed. Luna runs only after Core authorizes the reasoning request; external actions remain dry-run.",
            )
        if self._semantic_actions:
            # Swap only the ACTION tool in this explicitly opt-in experiment.
            # The conversation/sleep/Luna route, VAD and PCM pipeline are unchanged.
            policy['tools'] = [t for t in policy['tools'] if t.get('name') != 'test_action']
            policy['tools'].append({
                'type':'function', 'name':'browser_action',
                'description':('For a real, immediate user request to open YouTube or find a video on YouTube. '
                               'Understand any natural wording, including longer conversational requests. '
                               'Use open to show the YouTube homepage; use search to show YouTube search results '
                               'with a concise search query only from established conversation context; if missing, ask for clarification. '
                               'Never call for negated, quoted, conditional or hypothetical requests. '
                               'Do not claim completion; Core independently checks consent and destination.'),
                'parameters':{'type':'object','properties':{
                    'site':{'type':'string','enum':['youtube']},
                    'intent':{'type':'string','enum':['open','search']},
                    'query':{'type':'string','description':'Search terms if intent is search. Do not provide a URL.'}
                },'required':['site','intent'],'additionalProperties':False}
            })
            policy['instructions'] = str(policy['instructions']).replace(
                'For external actions use test_action (dry run).',
                'For an immediate request to open YouTube or find a video there, call browser_action. '
                'Never claim execution; Core verifies the user request and the exact destination. '
                'Other external actions remain unsupported.')
        print(f"[Jarvis A/B Start] model={self.config.model} | reasoning={self.config.reasoning_effort} | "
              f"mode={'overlap_probe' if overlap_probe else ('buffered_tool_probe' if buffered_probe else ('tool_probe_text_only' if tool_probe else ('direct_no_gate_tools_disabled' if direct_only else 'safe_routed')))} | "
              f"shadow={self.config.parallel_shadow_probe and not direct_only} | "
              "pricing=estimates_only | core_cost=excluded", flush=True)
        await websocket.send_json({
            "kind": "response_policy",
            "parallel_shadow_probe": self.config.parallel_shadow_probe and not direct_only,
            "direct_only_benchmark": direct_only,
            "tool_selection_probe": tool_probe,
            "buffered_tool_probe": buffered_probe,
            "overlap_probe": overlap_probe,
            "core_luna_probe": self.config.core_luna_probe,
            "delegation_guidance_probe": self.config.delegation_guidance_probe,
            "core_actions_probe": self._actions_enabled,
            "semantic_actions_probe": self._semantic_actions,
            "pcm_trim_leading_silence": overlap_probe and str(merged_environment(PROJECT_ROOT / ".env").get("JARVIS_PCM_TRIM_LEADING_SILENCE", "0")).lower() in {"1", "true", "yes", "on"},
            "response": policy,
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
                if kind == "desktop_overlap_audio" and self._action_session is not None and message.get("phase") == "started":
                    self._action_session.on_turn_started(int(message.get("turn") or 0))
                    # Existing latency handling below still sees this event.
                if kind == "desktop_action_request":
                    if self._action_session is None:
                        continue
                    turn = int(message.get("turn") or 0)
                    result = await self._action_session.handle(
                        turn=turn, selected_tool=str(message.get("selected_tool") or ""),
                        source=str(message.get("source") or ""),
                        binding=str(message.get("binding") or ""),
                        transcript=message.get("text"),
                        **({"arguments": message.get("arguments")} if self._semantic_actions else {}))
                    if result is not None:
                        print(f"[Jarvis Action] turn={turn} | tool=desktop_browser "
                              f"| status={result.status} | code={result.code} | authority=core", flush=True)
                        await relay.notify_desktop({'kind':'core_tool_result', 'turn':turn,
                            'status':result.status, 'text':result.text})
                    continue
                if kind == "desktop_action_feedback":
                    # UI-only acknowledgment. Never execute/retry an action from
                    # this message; print it to diagnose a stuck Working state.
                    turn = int(message.get("turn") or 0)
                    raw_status = str(message.get("status") or "unknown")
                    status = raw_status if raw_status in {"completed", "failed", "unknown"} else "unknown"
                    print(f"[Jarvis Action UI] turn={turn} | status={status} "
                          f"| visible_confirmation={message.get('visible_confirmation') is True} "
                          f"| spoken={message.get('spoken') is True} "
                          f"| reason={'result_timeout' if message.get('reason') == 'result_timeout' else 'core_result'}",
                          flush=True)
                    continue
                if kind == "desktop_user":
                    turn = int(message.get("turn") or 0)
                    source = str(message.get("source") or "unknown")
                    print(
                        f"[USER SPEECH] turn={turn or 'n/a'} | realtime_model={self.config.model} | source={source} | text={_terminal_chat_text(message.get('text'))}",
                        flush=True,
                    )
                    self._bench.on_user(turn, str(message.get("text") or ""))
                    if self._luna is not None and source in {"voice", "typed", "wake_transcript"}:
                        self._luna.transcript(turn, str(message.get("text") or ""))
                    if self._decisions_shadow is not None and source in {"voice", "typed", "wake_transcript"}:
                        self._decisions_shadow.observe_transcript(turn, str(message.get("text") or ""), transcript_ms=message.get("transcript_ms"))
                    if self._parallel_probe is not None and source in {"voice", "typed", "wake_transcript"}:
                        print(
                            f"[Jarvis Parallel] turn={turn or 'n/a'} | candidate=luna | transcript_ms={message.get('transcript_ms', 'n/a')}",
                            flush=True,
                        )
                        self._parallel_probe.on_transcript(turn, str(message.get("text") or ""))
                    continue
                if kind == "desktop_parallel_realtime":
                    if self.config.parallel_shadow_probe:
                        print(
                            f"[Jarvis Parallel] turn={int(message.get('turn') or 0)} | candidate=realtime_text | "
                            f"status={str(message.get('status') or 'unknown')} | "
                            f"elapsed_ms={message.get('elapsed_ms', 'n/a')} | "
                            f"first_token_ms={message.get('first_token_ms', 'n/a')} | "
                            f"text_tokens={message.get('text_tokens', 'n/a')} | "
                            f"audio_tokens={message.get('audio_tokens', 'n/a')}",
                            flush=True,
                        )
                    continue
                if kind == "desktop_reply":
                    turn = int(message.get("turn") or 0)
                    source = str(message.get("source") or "unknown")
                    print(
                        f"[JARVIS REPLY] turn={turn or 'n/a'} | realtime_model={self.config.model} | source={source} | text={_terminal_chat_text(message.get('text'))}",
                        flush=True,
                    )
                    if self._decisions_shadow is not None:
                        self._decisions_shadow.observe_reply(turn, str(message.get("text") or ""))
                    print(self._bench.on_reply(turn, str(message.get("text") or "")), flush=True)
                    continue
                if kind == "desktop_luna_voice":
                    if self._luna is not None:
                        print(f"[Jarvis Luna Voice] turn={message.get('turn','n/a')} | "
                              f"phase={message.get('phase','n/a')} | "
                              f"reason={message.get('reason','n/a')} | "
                              f"core_text_chars={message.get('core_text_chars','n/a')} | "
                              f"voice_delivered={message.get('voice_delivered','n/a')}", flush=True)
                    continue
                if kind == "desktop_luna_cancel_cue":
                    if self._luna is not None and self.config.luna_result_hold_seconds:
                        print(f"[Jarvis Luna Cancel Test] turn={int(message.get('turn') or 0)} "
                              f"| phase=cue_ack | audio_scheduled={message.get('audible') is True}", flush=True)
                    continue
                if kind == "desktop_luna_cancel":
                    if self._luna is not None:
                        await self._luna.cancel()
                    continue
                if kind == "desktop_overlap_audio":
                    if self._luna is not None:
                        turn = int(message.get("turn") or 0)
                        phase = str(message.get("phase") or "")
                        if phase == "started":
                            self._luna.new_turn(turn)
                        elif phase == "sleep":
                            await self._luna.cancel()
                    if self._decisions_shadow is not None:
                        phase = str(message.get("phase") or "")
                        if phase in {"direct", "sleep"}:
                            self._decisions_shadow.observe_mini_route(int(message.get("turn") or 0), phase)
                    if message.get("phase") == "latency_breakdown":
                        fields = ("commit_ms", "transcript_ms", "route_ms", "candidate_created_ms",
                                  "pcm_ready_ms", "gate_authorized_ms", "first_audio_ms",
                                  "pcm_signal_ms", "pcm_buffer_ready_ms", "signal_to_first_audio_ms",
                                  "authorized_to_first_audio_ms", "pcm_trim_enabled")
                        details = " | ".join(f"{key}={message.get(key, 'n/a')}" for key in fields)
                        print(f"[Jarvis Latency Detail] turn={message.get('turn','n/a')} | {details}", flush=True)
                        continue
                    print(f"[Jarvis Overlap] turn={message.get('turn','n/a')} | phase={message.get('phase','n/a')} | "
                          f"decision_ms={message.get('decision_ms','n/a')} | "
                          f"first_playback_ms={message.get('first_playback_ms','n/a')} | "
                          f"commit_wait_ms={message.get('commit_wait_ms','n/a')} | "
                          f"input_binding={message.get('input_binding','n/a')} | "
                          f"reason={message.get('reason','n/a')}", flush=True)
                    continue
                if kind == "desktop_buffered_audio":
                    print(f"[Jarvis Buffered Audio] turn={message.get('turn','n/a')} | phase={message.get('phase','n/a')} | "
                          f"selected={message.get('selected','n/a')} | capture_ms={message.get('capture_ms','n/a')} | "
                          f"first_playback_ms={message.get('first_playback_ms','n/a')} | reason={message.get('reason','n/a')}", flush=True)
                    continue
                if kind == "desktop_tool_probe":
                    turn = int(message.get("turn") or 0)
                    tool = str(message.get("tool") or "unknown")
                    phase = str(message.get("phase") or "unknown")
                    approved = tool in ALLOWED_PROBE_TOOLS
                    if self._decisions_shadow is not None and phase == "selection" and approved:
                        self._decisions_shadow.observe_mini_route(turn, tool)
                    live_luna = self._luna is not None and phase == "selection" and tool == "ask_luna"
                    delegated = self._luna.selected(turn) if live_luna else False
                    if live_luna:
                        print(f"[Jarvis Luna] turn={turn} | phase=selection | queued={delegated} "
                              "| request_source=confirmed_user_transcript | other_tools=dry_run", flush=True)
                    print(f"[Jarvis Tool Probe] turn={turn or 'n/a'} | tool={tool} | "
                          f"phase={phase} | dry_run={not delegated} | executed=False | permitted={approved} | "
                          f"pretool_text_chars={message.get('pretool_text_chars', 'n/a')} | "
                          f"decision_ms={message.get('decision_ms', 'n/a')}", flush=True)
                    if phase == 'selection' and approved:
                        self._bench.on_core(turn, "core_luna" if delegated else f"dry_run:{tool}")
                    continue
                if kind == "desktop_fast_direct":
                    turn = int(message.get("turn") or 0)
                    self._bench.on_route(turn, "direct_no_gate")
                    print(f"[Jarvis Fast A/B] turn={turn} | model={self.config.model} | "
                          "route=none | owner=realtime | tools=disabled | core=disabled", flush=True)
                    continue
                if kind == "desktop_route":
                    turn = int(message.get("turn") or 0)
                    route = str(message.get("route") or "unknown")
                    call_id = str(message.get("call_id") or "").strip()
                    route_ms = message.get("speech_end_to_route_ms")
                    route_metric = "n/a" if route_ms is None else f"{route_ms} ms"
                    self._bench.on_route(turn, route)
                    if route not in {"direct", "sleep"}:
                        self._bench.on_core(turn, f"core:{route}")
                    if call_id and turn > 0:
                        bridge.note_route_telemetry(call_id=call_id, turn=turn)
                    if self._parallel_probe is not None:
                        self._parallel_probe.on_route(turn, route)
                    owner = "realtime" if route == "direct" else ("lifecycle" if route == "sleep" else "core")
                    print(
                        f"[Jarvis Route] turn={turn or 'n/a'} | route={route} | owner={owner} | route_ms={route_metric} | call_id={call_id or 'n/a'}",
                        flush=True,
                    )
                    if route == "direct":
                        print(
                            f"[Jarvis Direct] turn={turn or 'n/a'} | realtime-only | call_id={call_id or 'n/a'}",
                            flush=True,
                        )
                    continue
                if kind == "desktop_latency":
                    turn = message.get("turn")
                    def metric(name: str) -> str:
                        value = message.get(name)
                        return "n/a" if value is None else f"{value} ms"
                    self._bench.on_latency(int(turn or 0), message.get("speech_end_to_first_audio_ms"))
                    if self._decisions_shadow is not None:
                        self._decisions_shadow.observe_voice_timing(
                            int(turn or 0),
                            speech_end_to_route_ms=message.get("speech_end_to_route_ms"),
                            speech_end_to_first_audio_ms=message.get("speech_end_to_first_audio_ms"),
                        )
                    print(
                        "[Desktop latency] "
                        f"turn={turn} | "
                        f"route={message.get('route') or 'n/a'} | "
                        f"speech_end->route={metric('speech_end_to_route_ms')} | "
                        f"route->first_audio={metric('route_to_first_audio_ms')} | "
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
                if self.config.direct_only_benchmark and str(event.get("type") or "") == "response.function_call_arguments.done":
                    print(f"[Jarvis Fast A/B Guard] blocked unexpected function call: "
                          f"{str(event.get('name') or 'unknown')}", flush=True)
                    # Defense in depth: do not forward forbidden tool execution.
                    continue
                if str(event.get("type") or "") == "response.function_call_arguments.done":
                    tool_name = str(event.get("name") or "unknown")
                    call_id = str(event.get("call_id") or "n/a")
                    print(f"[Jarvis A/B Tool] turn={self._bench.active_turn or 'n/a'} | "
                          f"model={self.config.model} | tool={tool_name} | call_id={call_id}", flush=True)
                    if tool_name == "delegate_to_jarvis_core":
                        self._bench.on_core(self._bench.active_turn, tool_name)
                if str(event.get("type") or "") == "response.done" and isinstance(event.get("response"), dict):
                    response = event["response"]
                    details = response.get("status_details")
                    reason = None
                    if isinstance(details, dict):
                        reason = details.get("reason") or details.get("type")
                    metadata = response.get("metadata") if isinstance(response.get("metadata"), dict) else {}
                    stage = str(metadata.get("jarvis_stage") or "answer_or_tool")
                    model_turn = int(metadata.get("jarvis_turn") or self._bench.active_turn or 0)
                    usage_line = self._bench.on_response(response, turn=model_turn, stage=stage)
                    if usage_line: print(usage_line, flush=True)
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
                if not self.config.tool_selection_probe:
                    if not self.config.buffered_tool_probe:
                        if not self.config.overlap_probe:
                            await relay.feed_event(event)
                # Tool-selection probe never forwards calls to the trusted bridge.
                # Its simulated outputs are produced locally in the renderer.
        except WebSocketDisconnect:
            pass
        finally:
            if not sender_task.done():
                sender_task.cancel()
            await asyncio.gather(sender_task, return_exceptions=True)
            print(self._bench.summary(), flush=True)
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
            include_input_transcription=self.config.desktop_conversation_trace,
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
            parallel_probe = self._parallel_probe
            self._parallel_probe = None
            decisions_shadow = self._decisions_shadow
            self._decisions_shadow = None
            luna = self._luna
            self._luna = None
            self._relay = None
            self._bridge = None
            self._event_task = None

        if call_id:
            with suppress(Exception):
                await hangup_realtime_call(self.config, call_id)
        if parallel_probe is not None:
            with suppress(Exception):
                await parallel_probe.close()
        if decisions_shadow is not None:
            with suppress(Exception):
                await decisions_shadow.close()
        if luna is not None:
            with suppress(Exception):
                await luna.close()
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
    delegation_orchestrator: DelegationOrchestrator | None = None,
    additional_providers: tuple[OpenAIProvider, ...] = (),
) -> FastAPI:
    version = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    session = DesktopRealtimeSession(
        runtime=runtime,
        config=realtime_config,
        delegation_orchestrator=delegation_orchestrator,
    )
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
            closed: set[int] = set()
            for backend_provider in (provider, *additional_providers):
                if id(backend_provider) in closed:
                    continue
                closed.add(id(backend_provider))
                await backend_provider.close()
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
            "delegation_router": delegation_orchestrator is not None,
            "conversation_trace": realtime_config.desktop_conversation_trace,
            "backend_routes": [route.name for route in runtime.provider_router.routes()],
        }

    @app.get("/api/desktop/config")
    async def desktop_config() -> dict[str, Any]:
        return {
            "version": version,
            "model": realtime_config.model,
            "voice": realtime_config.voice,
            "reasoning_effort": realtime_config.reasoning_effort,
            "conversation_trace": realtime_config.desktop_conversation_trace,
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
    _configure_terminal_output()
    args = parser().parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("[FAIL] 0.1.1 Desktop Alpha host is loopback-only")
    if not 1024 <= args.port <= 65535:
        raise SystemExit("[FAIL] --port must be between 1024 and 65535")

    runtime, provider, backend_providers, delegation_orchestrator = build_runtime()
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
        delegation_orchestrator=delegation_orchestrator,
        additional_providers=tuple(item for item in backend_providers if item is not provider),
    )
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
