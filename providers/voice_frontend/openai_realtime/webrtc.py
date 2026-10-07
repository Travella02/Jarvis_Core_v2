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

from core.conversation.persona import JARVIS_CONCISE_EXAMPLES, JARVIS_PERSONALITY_INSTRUCTIONS
from core.voice.webrtc import normalize_sdp
from providers.voice_frontend.openai_realtime.config import OpenAIRealtimeConfig


DELEGATE_TOOL_NAME = "delegate_to_jarvis_core"
ROUTE_TURN_TOOL_NAME = "route_jarvis_turn"
SLEEP_TOOL_NAME = "sleep_jarvis"
EXPAND_RESPONSE_TOOL_NAME = "request_expanded_response"
DEFAULT_REALTIME_MAX_OUTPUT_TOKENS = 1024
EXPANDED_REALTIME_MAX_OUTPUT_TOKENS = 2048
DESKTOP_REALTIME_MAX_OUTPUT_TOKENS = 2048

REALTIME_CONVERSATION_INSTRUCTIONS = f"""You are Jarvis's realtime conversational layer.
Your priority is natural, human conversation: quick turn-taking, useful emotion, immediate interruption handling, and disciplined spoken length.

{JARVIS_PERSONALITY_INSTRUCTIONS}

Direct-answer policy:
- Answer ordinary conversation, general knowledge, simple explanations, jokes, and other things you can answer confidently directly.
- Do not pretend to look something up when you already know it. For a simple factual question, answer it naturally instead of saying filler such as 'just a sec'.

Jarvis Core delegation policy:
- Use delegate_to_jarvis_core when the request depends on the user's durable memory, private/project context, files, current application state, permissions, actions, tools, or background tasks.
- Delegate when deeper or longer reasoning would materially improve the answer, or when you are uncertain enough that Jarvis Core should route to a stronger model.
- Preserve the user's constraints faithfully in the delegated request. Never claim a delegated action or result succeeded before Core returns it.

Delegation speech discipline:
- When you decide to call delegate_to_jarvis_core, that tool call must be the initial output for the response. Do not speak an acknowledgement, plan, or filler before the tool call.
- Never say or imply that an action, background task, search, lookup, or other delegated capability is starting, queued, prepared, possible, or completed until Jarvis Core returns an authoritative result confirming that state.
- The desktop WORKING state is the acknowledgement while delegated work is pending. After Core returns, speak only the verified result.
- While Core is working, remain available for interruption or follow-up. If asked about a pending result, say that it is still in progress rather than inventing an answer.

Internal implementation privacy:
- Core, delegation, backend routing, tool calls, model/provider selection, and internal layers are implementation details. Never narrate or name them in a user-facing response unless the user is explicitly asking how Jarvis is architected.
- If a user says something like 'use your Core' as part of an ordinary task request, treat that only as an internal routing preference. Do not echo it, announce it, or say that you are pulling in Core. Start with the useful result once it is available.
- Never expose phrases such as 'talking to Core', 'delegating this', 'routing this', 'calling a tool', or 'using the backend' as conversational filler.

Natural acknowledgement policy:
- A brief acknowledgement such as 'Sure, I'm on it' can still be natural for work that does not require a Core delegation, but do not add waiting language before an answer you can give immediately.
- A brief reaction, dry observation, or bit of wit is welcome when it fits, but it must flow directly into the useful answer rather than becoming filler.

Spoken-length policy (high priority):
- Response-specific instructions may impose a concise conversational shape for an individual turn. Follow those response instructions precisely.
- For ordinary questions, give the shortest natural answer that fully answers the user.
- Brief continuation questions such as 'why?', 'why does that happen?', 'how?', or 'what do you mean?' ask only for the missing point. Do not restart the earlier explanation or add unrelated background.
- Do not add a second analogy, unsolicited related fact, recap, or invitation to continue once the answer is complete.
- Preserve personality inside the concise answer. Concise must never mean flat, robotic, or personality-free.
- If the user explicitly asks for detail, depth, examples, a walkthrough, a deep dive, a thorough explanation, or otherwise clearly requests a long answer, follow the response-specific instructions for that turn. In the desktop manual-response path, answer the detailed response directly in one continuous response; do not add a separate waiting acknowledgement first. The request_expanded_response tool remains only as a compatibility path for older/automatic labs.

{JARVIS_CONCISE_EXAMPLES}

Sleep lifecycle policy:
- When the user clearly ends the interaction or explicitly asks Jarvis to sleep (for example, "that's all", "go to sleep", or "good night Jarvis"), call sleep_jarvis immediately as the only response.
- For clear sleep intent, produce no spoken acknowledgement, filler, or normal answer before or after the sleep_jarvis tool call. The lifecycle transition itself is the acknowledgement.
- Do not use sleep_jarvis for ordinary pauses, interruptions, "stop" inside another task, or ambiguous language.

When Jarvis Core returns a function result, communicate it naturally and faithfully. Core remains authoritative for memory, permissions, tool outcomes, tasks, and verified facts returned by delegated work.
"""


NORMAL_RESPONSE_INSTRUCTIONS = f"""This response is an ordinary conversational turn.
Lifecycle/tool control has higher priority than spoken formatting:
- If the user clearly ends the interaction or asks Jarvis to sleep (for example, "that's all", "that's all Jarvis", "go to sleep", or "good night Jarvis"), do not speak; call sleep_jarvis immediately as the initial and only output of this response.
- Never acknowledge an explicit sleep request with words such as "got it", "signing off", or "good night" before calling sleep_jarvis. The silent lifecycle transition is the acknowledgement.
- If the request requires durable/private context, tools, permissions, actions, background work, or stronger backend reasoning, use delegate_to_jarvis_core rather than pretending the work is complete.
- If the user explicitly asked for a detailed, thorough, deep, step-by-step, example-rich, or otherwise intentionally long answer, answer that detailed request directly in this same response. Do not call request_expanded_response from the desktop manual-response path; enough safety headroom is already provided.
- For a detailed direct answer, begin the useful answer immediately. At most one brief natural lead-in is allowed. Never say you need a moment, need to think, or are about to explain something and then restart with a second acknowledgement. Waiting language is only appropriate when real backend work is actually pending.

For an ordinary direct spoken answer, answer in at most two complete spoken sentences and normally no more than about 35 words. This is a response-format constraint, not a suggestion.
Answer only the point the user asked for; do not restart prior context, add a second example, recap, or invite the user to continue.
Keep Jarvis's wit, warmth, confidence, and natural reactions inside that compact answer. Never become robotic just to be short.
Always finish the sentence you start. Do not trail off.
{JARVIS_CONCISE_EXAMPLES}
"""


TURN_ROUTER_INSTRUCTIONS = """This is an internal routing pass. Do not answer the user in this response.
Call route_jarvis_turn exactly once and make that function call the only semantic output.
Choose direct for ordinary conversation/general knowledge that the realtime layer can answer immediately.
Choose reasoning when the user explicitly asks to use Jarvis Core or when deeper backend reasoning is needed.
Choose memory for durable/private memory retrieval, action for external/device/tool execution, current_data for fresh external information, long_task for durable/background work, and sleep only for a clear request to end the Jarvis interaction.
Preserve the user's actual request faithfully in the request field. Never include a spoken acknowledgement, plan, filler, or user-facing prose in this routing pass.
"""

DIRECT_ROUTED_RESPONSE_INSTRUCTIONS = f"""The silent routing pass selected a direct realtime answer.
Answer the user's latest request now. Start with the useful answer itself; do not mention routing, Core, tools, models, providers, or the routing function.
Do not say 'let me think', 'let me check', 'give me a moment', or any other waiting/filler phrase.
For an ordinary direct spoken answer, answer in at most two complete spoken sentences and normally no more than about 35 words unless the user explicitly requested detail. Always finish the sentence you start.
{JARVIS_PERSONALITY_INSTRUCTIONS}
{JARVIS_CONCISE_EXAMPLES}
"""

CORE_RESULT_RESPONSE_INSTRUCTIONS = f"""Authoritative work has returned a verified result.
Read the function result status first and present only what was actually verified. Never describe an unavailable, failed, cancelled, or superseded capability as started, queued, prepared, attempted successfully, or completed.
If the status is unavailable, state the limitation plainly and stop; do not invent a workaround, ask for implementation details, or imply the work can begin in this build unless the user specifically asks for planning.
Present completed useful results naturally and faithfully in at most two compact spoken sentences unless the user explicitly requested a detailed result. Do not repeat the request or narrate Core, delegation, backend routing, tools, models, or providers.
Keep Jarvis's personality intact; concise means efficient, not flat.
{JARVIS_PERSONALITY_INSTRUCTIONS}
"""

EXPANDED_RESPONSE_INSTRUCTIONS = f"""The user explicitly asked for a detailed or expanded answer.
Use the larger response budget for this response only. Give the requested depth cleanly and naturally without mentioning budgets, tools, routing, or this instruction.
{JARVIS_PERSONALITY_INSTRUCTIONS}
"""


ROUTE_TURN_TOOL = {
    "type": "function",
    "name": ROUTE_TURN_TOOL_NAME,
    "description": (
        "Internal pre-speech router. Classify the latest user turn before any audible answer is allowed. "
        "This function call is never narrated to the user."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "route": {
                "type": "string",
                "enum": ["direct", "reasoning", "memory", "action", "current_data", "long_task", "sleep"],
                "description": "The single route that should own this turn before any user-facing speech.",
            },
            "request": {
                "type": "string",
                "description": "A faithful, self-contained statement of the user's actual request, preserving constraints.",
            },
        },
        "required": ["route", "request"],
        "additionalProperties": False,
    },
}

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
                "enum": ["reasoning", "memory", "action", "current_data", "long_task"],
                "description": "Why Core is needed. This is a capability category only; Core remains free to choose the actual model/tool/provider route.",
            },
        },
        "required": ["request", "mode"],
        "additionalProperties": False,
    },
}

SLEEP_TOOL = {
    "type": "function",
    "name": SLEEP_TOOL_NAME,
    "description": (
        "Put Jarvis into the local sleeping presence state only when the user clearly ends the interaction "
        "or explicitly asks Jarvis to sleep. This closes the paid Realtime session while the local wake listener remains armed."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Short lifecycle reason such as user_done or explicit_sleep.",
            }
        },
        "required": [],
        "additionalProperties": False,
    },
}


EXPAND_RESPONSE_TOOL = {
    "type": "function",
    "name": EXPAND_RESPONSE_TOOL_NAME,
    "description": (
        "Request a larger spoken-response budget only when the user explicitly asks for a detailed, thorough, "
        "deep, example-rich, step-by-step, or otherwise intentionally long explanation. Never use this for an "
        "ordinary question or a short follow-up such as why/how/what do you mean."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Very short reason the user explicitly requested an expanded answer.",
            }
        },
        "required": [],
        "additionalProperties": False,
    },
}

class RealtimeWebRTCSessionCreationError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, request_id: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id


def build_realtime_session(
    config: OpenAIRealtimeConfig,
    *,
    auto_create_response: bool = True,
    include_expand_response_tool: bool = True,
) -> dict[str, Any]:
    tools = [DELEGATE_TOOL, SLEEP_TOOL]
    if include_expand_response_tool:
        tools.append(EXPAND_RESPONSE_TOOL)
    return {
        "type": "realtime",
        "model": config.model,
        "instructions": REALTIME_CONVERSATION_INSTRUCTIONS,
        "output_modalities": ["audio"],
        "max_output_tokens": DEFAULT_REALTIME_MAX_OUTPUT_TOKENS,
        "audio": {
            "input": {
                "turn_detection": {
                    "type": "semantic_vad",
                    "create_response": auto_create_response,
                    "interrupt_response": True,
                }
            },
            "output": {"voice": config.voice},
        },
        "reasoning": {"effort": config.reasoning_effort},
        "tools": tools,
        "tool_choice": "auto",
    }


async def create_realtime_webrtc_call(
    config: OpenAIRealtimeConfig,
    offer_sdp: str,
    *,
    client: httpx.AsyncClient | None = None,
    url: str | None = None,
    auto_create_response: bool = True,
    include_expand_response_tool: bool = True,
) -> tuple[str, str]:
    if not config.api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    clean_sdp = normalize_sdp(offer_sdp, label="Realtime WebRTC SDP offer")
    session_json = json.dumps(
        build_realtime_session(
            config,
            auto_create_response=auto_create_response,
            include_expand_response_tool=include_expand_response_tool,
        ),
        separators=(",", ":"),
    )

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

    async def send_function_output(
        self,
        call_id: str,
        output: Mapping[str, Any],
        *,
        continue_response: bool = True,
        response_overrides: Mapping[str, Any] | None = None,
    ) -> None:
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
            event: dict[str, Any] = {"type": "response.create"}
            if response_overrides:
                event["response"] = dict(response_overrides)
            await self._outgoing.put({"kind": "realtime_send", "event": event})

    async def request_browser_sleep(self, *, reason: str = "explicit_sleep") -> None:
        if not self._closed:
            await self._outgoing.put({"kind": "lifecycle_command", "command": "sleep", "reason": reason})

    async def request_browser_close(self) -> None:
        if not self._closed:
            await self._outgoing.put({"kind": "lab_command", "command": "close"})

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._events.put(None)
        await self._outgoing.put(None)
