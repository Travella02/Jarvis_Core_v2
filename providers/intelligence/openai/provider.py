"""OpenAI implementation of the provider-neutral IntelligenceProvider contract."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any

from core.common.cancellation import CancellationToken
from core.intelligence import (
    ContextLimits,
    IntelligenceContext,
    IntelligenceEvent,
    IntelligenceEventType,
    IntelligenceProvider,
    ProviderHealth,
    ProviderHealthState,
    ProviderMetadata,
    ReasoningPolicy,
)
from core.tools import ToolDefinition, ToolRequest
from providers.intelligence.openai.config import DEFAULT_MODEL, OpenAIProviderConfig
from providers.intelligence.openai.serialization import (
    parse_tool_arguments,
    reasoning_effort,
    serialize_messages,
    serialize_tools,
)


class OpenAIProviderError(RuntimeError):
    """Base adapter error that never exposes secrets."""


class OpenAIProviderNotConfigured(OpenAIProviderError):
    pass


class OpenAISDKUnavailable(OpenAIProviderError):
    pass


@dataclass(slots=True)
class _ActiveRequest:
    token: CancellationToken
    stream: Any | None = None
    transport: str = "http"


@dataclass(slots=True)
class _VoiceLaneState:
    previous_response_id: str
    input_messages: tuple[dict[str, Any], ...]
    assistant_text: str
    stream_id: str


class OpenAIProvider(IntelligenceProvider):
    """GPT-5.6 Luna adapter using the OpenAI Responses API.

    HTTP remains the general provider path. Voice Lab may opt into a persistent
    Responses WebSocket connection. The WebSocket continuation cache is purely a
    transport optimization: Conversation Core remains authoritative. Continuation
    is used only when the next Core snapshot exactly extends the previously
    completed provider turn; any mismatch resets to a full-context request.
    """

    _LUNA_LIMITS = ContextLimits(max_input_tokens=1_050_000, max_output_tokens=128_000)

    def __init__(
        self,
        config: OpenAIProviderConfig,
        *,
        client: Any | None = None,
    ) -> None:
        self.config = config
        self._client = client
        self._owns_client = client is None
        self._active: dict[str, _ActiveRequest] = {}
        self._last_error: str | None = None
        self._successful_request_seen = False
        self._voice_connection: Any | None = None
        self._voice_connection_manager: Any | None = None
        self._voice_connection_lock = asyncio.Lock()
        self._voice_request_lock = asyncio.Lock()
        self._voice_lanes: dict[str, _VoiceLaneState] = {}

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(provider="openai", model=self.config.model, model_snapshot=None)

    def supports_tools(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return True

    def supports_reasoning_levels(self) -> bool:
        return True

    def context_limits(self) -> ContextLimits:
        if self.config.model == DEFAULT_MODEL:
            return self._LUNA_LIMITS
        return ContextLimits()

    async def health(self) -> ProviderHealth:
        if not self.config.api_key and self._client is None:
            return ProviderHealth(
                state=ProviderHealthState.NOT_CONFIGURED,
                detail="OPENAI_API_KEY is not configured",
            )
        if self._client is None and importlib.util.find_spec("openai") is None:
            return ProviderHealth(
                state=ProviderHealthState.UNAVAILABLE,
                detail="OpenAI Python SDK is not installed",
            )
        if self._last_error:
            return ProviderHealth(state=ProviderHealthState.DEGRADED, detail=self._last_error)
        if self._successful_request_seen:
            return ProviderHealth(
                state=ProviderHealthState.HEALTHY,
                detail="At least one provider request completed successfully",
            )
        return ProviderHealth(
            state=ProviderHealthState.CONFIGURED,
            detail="Configured locally; no live request has completed in this process",
        )

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.config.api_key:
            raise OpenAIProviderNotConfigured("OPENAI_API_KEY is not configured")
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise OpenAISDKUnavailable(
                "OpenAI Python SDK is not installed. Install project dependencies first."
            ) from exc

        kwargs: dict[str, Any] = {
            "api_key": self.config.api_key,
            "timeout": self.config.timeout_seconds,
        }
        if self.config.base_url:
            kwargs["base_url"] = self.config.base_url
        if self.config.organization:
            kwargs["organization"] = self.config.organization
        if self.config.project:
            kwargs["project"] = self.config.project
        self._client = AsyncOpenAI(**kwargs)
        return self._client

    def _request_params(
        self,
        context: IntelligenceContext,
        tools: Sequence[ToolDefinition],
        reasoning_policy: ReasoningPolicy,
        *,
        websocket: bool = False,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self.config.model,
            "input": serialize_messages(context),
            "reasoning": {"effort": reasoning_effort(reasoning_policy, self.config)},
            "max_output_tokens": self.config.max_output_tokens,
            "store": self.config.store_responses,
        }
        if not websocket:
            params["stream"] = True
        if context.metadata.get("input_channel") == "voice":
            params["text"] = {"verbosity": "low"}
            params["max_output_tokens"] = self.config.voice_max_output_tokens
            params["prompt_cache_options"] = {"mode": "implicit", "ttl": "30m"}
        if self.config.service_tier != "auto":
            params["service_tier"] = self.config.service_tier

        serialized_tools = serialize_tools(tools)
        if serialized_tools:
            params["tools"] = serialized_tools
            params["parallel_tool_calls"] = True
        return params

    def _use_voice_websocket(
        self,
        context: IntelligenceContext,
        tools: Sequence[ToolDefinition],
    ) -> bool:
        return (
            self.config.voice_transport == "websocket"
            and context.metadata.get("input_channel") == "voice"
            and not tools
        )

    async def stream_response(
        self,
        context: IntelligenceContext,
        tools: Sequence[ToolDefinition],
        reasoning_policy: ReasoningPolicy,
        cancellation_token: CancellationToken,
    ) -> AsyncIterator[IntelligenceEvent]:
        if self._use_voice_websocket(context, tools):
            async for item in self._stream_response_websocket(
                context, tools, reasoning_policy, cancellation_token
            ):
                yield item
            return
        async for item in self._stream_response_http(
            context, tools, reasoning_policy, cancellation_token
        ):
            yield item

    async def _stream_response_http(
        self,
        context: IntelligenceContext,
        tools: Sequence[ToolDefinition],
        reasoning_policy: ReasoningPolicy,
        cancellation_token: CancellationToken,
    ) -> AsyncIterator[IntelligenceEvent]:
        request_id = context.trace.request_id
        if cancellation_token.is_cancelled:
            yield IntelligenceEvent(
                event_type=IntelligenceEventType.CANCELLED,
                detail=cancellation_token.reason or "Request cancelled before provider start",
            )
            return
        if request_id in self._active:
            raise OpenAIProviderError(f"Request {request_id!r} is already active")

        active = _ActiveRequest(token=cancellation_token, transport="http")
        self._active[request_id] = active
        response_id: str | None = None
        terminal_emitted = False

        try:
            client = self._get_client()
            stream = await client.responses.create(
                **self._request_params(context, tools, reasoning_policy)
            )
            active.stream = stream

            async for event in stream:
                if cancellation_token.is_cancelled:
                    await self._close_stream(stream)
                    terminal_emitted = True
                    yield IntelligenceEvent(
                        event_type=IntelligenceEventType.CANCELLED,
                        detail=cancellation_token.reason or "Request cancelled",
                        provider_response_id=response_id,
                    )
                    break
                converted, response_id, terminal = self._convert_event(
                    event, context=context, response_id=response_id
                )
                for item in converted:
                    yield item
                if terminal:
                    terminal_emitted = True
                    break

            if cancellation_token.is_cancelled and not terminal_emitted:
                terminal_emitted = True
                yield IntelligenceEvent(
                    event_type=IntelligenceEventType.CANCELLED,
                    detail=cancellation_token.reason or "Request cancelled",
                    provider_response_id=response_id,
                )
            elif not terminal_emitted:
                self._successful_request_seen = True
                self._last_error = None
                yield IntelligenceEvent(
                    event_type=IntelligenceEventType.COMPLETED,
                    detail="Provider stream ended without an explicit completion event",
                    provider_response_id=response_id,
                )
        except OpenAIProviderError:
            raise
        except Exception as exc:
            detail = self._safe_exception_detail(exc)
            self._last_error = detail
            yield IntelligenceEvent(
                event_type=IntelligenceEventType.ERROR,
                detail=detail,
                provider_response_id=response_id,
            )
        finally:
            if active.stream is not None:
                await self._close_stream(active.stream)
            self._active.pop(request_id, None)

    async def _stream_response_websocket(
        self,
        context: IntelligenceContext,
        tools: Sequence[ToolDefinition],
        reasoning_policy: ReasoningPolicy,
        cancellation_token: CancellationToken,
    ) -> AsyncIterator[IntelligenceEvent]:
        request_id = context.trace.request_id
        if cancellation_token.is_cancelled:
            yield IntelligenceEvent(
                event_type=IntelligenceEventType.CANCELLED,
                detail=cancellation_token.reason or "Request cancelled before provider start",
            )
            return
        if request_id in self._active:
            raise OpenAIProviderError(f"Request {request_id!r} is already active")

        active = _ActiveRequest(token=cancellation_token, transport="websocket")
        self._active[request_id] = active
        response_id: str | None = None
        terminal_emitted = False
        text_parts: list[str] = []
        messages = tuple(dict(item) for item in serialize_messages(context))
        conversation_id = str(context.metadata.get("conversation_id") or request_id)

        async with self._voice_request_lock:
            try:
                connection = await self._get_voice_connection()
                active.stream = connection
                params = self._request_params(
                    context, tools, reasoning_policy, websocket=True
                )
                lane = self._voice_lanes.get(conversation_id)
                if lane is not None and self._can_continue_lane(lane, messages):
                    params["input"] = [messages[-1]]
                    params["previous_response_id"] = lane.previous_response_id
                    params["stream_id"] = lane.stream_id
                else:
                    self._voice_lanes.pop(conversation_id, None)
                    params["input"] = list(messages)
                    params["stream_id"] = self._stream_id(conversation_id)

                await connection.response.create(**params)

                async for event in connection:
                    if cancellation_token.is_cancelled:
                        await self._reset_voice_connection()
                        terminal_emitted = True
                        yield IntelligenceEvent(
                            event_type=IntelligenceEventType.CANCELLED,
                            detail=cancellation_token.reason or "Request cancelled",
                            provider_response_id=response_id,
                        )
                        break

                    event_type = getattr(event, "type", "")
                    if event_type == "response.output_text.delta":
                        delta = getattr(event, "delta", "")
                        if delta:
                            text_parts.append(str(delta))

                    converted, response_id, terminal = self._convert_event(
                        event, context=context, response_id=response_id
                    )
                    for item in converted:
                        yield item
                    if terminal:
                        terminal_emitted = True
                        if event_type == "response.completed" and response_id:
                            self._voice_lanes[conversation_id] = _VoiceLaneState(
                                previous_response_id=response_id,
                                input_messages=messages,
                                assistant_text="".join(text_parts).strip(),
                                stream_id=params["stream_id"],
                            )
                        else:
                            self._voice_lanes.pop(conversation_id, None)
                        break

                if not terminal_emitted:
                    self._voice_lanes.pop(conversation_id, None)
                    await self._reset_voice_connection()
                    yield IntelligenceEvent(
                        event_type=IntelligenceEventType.ERROR,
                        detail="OpenAI WebSocket response ended without a terminal event",
                        provider_response_id=response_id,
                    )
            except Exception as exc:
                # The persistent transport is an optimization, never a correctness
                # dependency. Before any text is emitted, fall back to the proven
                # HTTP path for this turn. Once output has started, fail closed to
                # avoid duplicating spoken content.
                self._voice_lanes.pop(conversation_id, None)
                await self._reset_voice_connection()
                if not text_parts:
                    self._last_error = None
                    self._active.pop(request_id, None)
                    async for item in self._stream_response_http(
                        context, tools, reasoning_policy, cancellation_token
                    ):
                        yield item
                    return
                detail = self._safe_exception_detail(exc)
                self._last_error = detail
                yield IntelligenceEvent(
                    event_type=IntelligenceEventType.ERROR,
                    detail=detail,
                    provider_response_id=response_id,
                )
            finally:
                self._active.pop(request_id, None)

    @staticmethod
    def _can_continue_lane(
        lane: _VoiceLaneState,
        messages: tuple[dict[str, Any], ...],
    ) -> bool:
        if not lane.assistant_text or len(messages) < 2:
            return False
        expected_prefix = lane.input_messages + (
            {"role": "assistant", "content": lane.assistant_text},
        )
        return (
            len(messages) == len(expected_prefix) + 1
            and messages[:-1] == expected_prefix
            and messages[-1].get("role") == "user"
        )

    @staticmethod
    def _stream_id(conversation_id: str) -> str:
        digest = hashlib.sha256(conversation_id.encode("utf-8")).hexdigest()[:24]
        return f"jarvis_voice_{digest}"

    async def _get_voice_connection(self) -> Any:
        if self._voice_connection is not None:
            return self._voice_connection
        async with self._voice_connection_lock:
            if self._voice_connection is not None:
                return self._voice_connection
            client = self._get_client()
            responses = getattr(client, "responses", None)
            connect = getattr(responses, "connect", None)
            if not callable(connect):
                raise OpenAISDKUnavailable(
                    "OpenAI SDK WebSocket transport is unavailable; install project dependencies"
                )
            manager = connect(max_retries=1)
            connection = await manager.enter()
            self._voice_connection_manager = manager
            self._voice_connection = connection
            return connection

    async def _reset_voice_connection(self) -> None:
        connection = self._voice_connection
        self._voice_connection = None
        self._voice_connection_manager = None
        self._voice_lanes.clear()
        if connection is not None:
            close = getattr(connection, "close", None)
            if callable(close):
                result = close()
                if hasattr(result, "__await__"):
                    await result

    def _convert_event(
        self,
        event: Any,
        *,
        context: IntelligenceContext,
        response_id: str | None,
    ) -> tuple[list[IntelligenceEvent], str | None, bool]:
        result: list[IntelligenceEvent] = []
        event_type = getattr(event, "type", "")
        if event_type == "response.created":
            response = getattr(event, "response", None)
            return result, getattr(response, "id", response_id), False

        if event_type == "response.output_text.delta":
            delta = getattr(event, "delta", "")
            if delta:
                result.append(
                    IntelligenceEvent(
                        event_type=IntelligenceEventType.TEXT_DELTA,
                        text_delta=str(delta),
                        provider_response_id=response_id,
                    )
                )
            return result, response_id, False

        if event_type == "response.output_item.done":
            item = getattr(event, "item", None)
            if getattr(item, "type", None) == "function_call":
                arguments = parse_tool_arguments(getattr(item, "arguments", "{}"))
                tool_request = ToolRequest(
                    trace=context.trace,
                    tool_name=str(getattr(item, "name")),
                    operation="invoke",
                    arguments=arguments,
                    provider_call_id=getattr(item, "call_id", None),
                )
                result.append(
                    IntelligenceEvent(
                        event_type=IntelligenceEventType.TOOL_REQUEST,
                        tool_request=tool_request,
                        provider_response_id=response_id,
                    )
                )
            return result, response_id, False

        if event_type == "response.completed":
            response = getattr(event, "response", None)
            response_id = getattr(response, "id", response_id)
            self._successful_request_seen = True
            self._last_error = None
            result.append(
                IntelligenceEvent(
                    event_type=IntelligenceEventType.COMPLETED,
                    provider_response_id=response_id,
                    metadata=self._completion_metadata(response),
                )
            )
            return result, response_id, True

        if event_type in {"response.failed", "error"}:
            detail = self._safe_error_detail(event)
            self._last_error = detail
            result.append(
                IntelligenceEvent(
                    event_type=IntelligenceEventType.ERROR,
                    detail=detail,
                    provider_response_id=response_id,
                )
            )
            return result, response_id, True

        if event_type == "response.incomplete":
            response = getattr(event, "response", None)
            response_id = getattr(response, "id", response_id)
            detail = "OpenAI response ended incomplete"
            self._last_error = detail
            result.append(
                IntelligenceEvent(
                    event_type=IntelligenceEventType.DEGRADED,
                    detail=detail,
                    provider_response_id=response_id,
                    metadata=self._completion_metadata(response),
                )
            )
            return result, response_id, True

        return result, response_id, False

    async def cancel(self, request_id: str) -> None:
        active = self._active.get(request_id)
        if active is None:
            return
        active.token.cancel("cancel() requested")
        if active.transport == "websocket":
            await self._reset_voice_connection()
        elif active.stream is not None:
            await self._close_stream(active.stream)

    async def close(self) -> None:
        await self._reset_voice_connection()
        client = self._client
        self._client = None
        if self._owns_client and client is not None:
            close = getattr(client, "close", None)
            if callable(close):
                result = close()
                if hasattr(result, "__await__"):
                    await result

    @staticmethod
    async def _close_stream(stream: Any) -> None:
        close = getattr(stream, "close", None)
        if callable(close):
            result = close()
            if hasattr(result, "__await__"):
                await result
            return
        response = getattr(stream, "response", None)
        aclose = getattr(response, "aclose", None)
        if callable(aclose):
            await aclose()

    @staticmethod
    def _completion_metadata(response: Any) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        if response is None:
            return metadata
        model = getattr(response, "model", None)
        if model:
            metadata["model"] = str(model)
        status = getattr(response, "status", None)
        if status:
            metadata["status"] = str(status)
        usage = getattr(response, "usage", None)
        if usage is not None:
            if hasattr(usage, "model_dump"):
                usage = usage.model_dump()
            elif hasattr(usage, "to_dict"):
                usage = usage.to_dict()
            if isinstance(usage, dict):
                metadata["usage"] = usage
        return metadata

    @staticmethod
    def _safe_error_detail(event: Any) -> str:
        error = getattr(event, "error", None)
        if error is None:
            response = getattr(event, "response", None)
            error = getattr(response, "error", None)
        code = getattr(error, "code", None) or getattr(event, "code", None)
        if code:
            return f"OpenAI response error ({code})"
        return "OpenAI response error"

    @staticmethod
    def _safe_exception_detail(exc: Exception) -> str:
        status = getattr(exc, "status_code", None)
        if status is not None:
            return f"OpenAI request failed with HTTP {status}"
        return f"OpenAI request failed ({exc.__class__.__name__})"
