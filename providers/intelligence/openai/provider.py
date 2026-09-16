"""OpenAI implementation of the provider-neutral IntelligenceProvider contract."""

from __future__ import annotations

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


class OpenAIProvider(IntelligenceProvider):
    """GPT-5.6 Luna adapter using the OpenAI Responses API.

    OpenAI SDK objects are deliberately contained in this provider package.
    Jarvis Core only sees provider-neutral contracts and streamed events.
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
        self._active: dict[str, _ActiveRequest] = {}
        self._last_error: str | None = None
        self._successful_request_seen = False

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
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self.config.model,
            "input": serialize_messages(context),
            "reasoning": {"effort": reasoning_effort(reasoning_policy, self.config)},
            "max_output_tokens": self.config.max_output_tokens,
            "store": self.config.store_responses,
            "stream": True,
        }
        serialized_tools = serialize_tools(tools)
        if serialized_tools:
            params["tools"] = serialized_tools
            params["parallel_tool_calls"] = True
        return params

    async def stream_response(
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

        active = _ActiveRequest(token=cancellation_token)
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

                event_type = getattr(event, "type", "")
                if event_type == "response.created":
                    response = getattr(event, "response", None)
                    response_id = getattr(response, "id", response_id)
                    continue

                if event_type == "response.output_text.delta":
                    delta = getattr(event, "delta", "")
                    if delta:
                        yield IntelligenceEvent(
                            event_type=IntelligenceEventType.TEXT_DELTA,
                            text_delta=str(delta),
                            provider_response_id=response_id,
                        )
                    continue

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
                        yield IntelligenceEvent(
                            event_type=IntelligenceEventType.TOOL_REQUEST,
                            tool_request=tool_request,
                            provider_response_id=response_id,
                        )
                    continue

                if event_type == "response.completed":
                    response = getattr(event, "response", None)
                    response_id = getattr(response, "id", response_id)
                    self._successful_request_seen = True
                    self._last_error = None
                    terminal_emitted = True
                    yield IntelligenceEvent(
                        event_type=IntelligenceEventType.COMPLETED,
                        provider_response_id=response_id,
                        metadata=self._completion_metadata(response),
                    )
                    continue

                if event_type in {"response.failed", "error"}:
                    detail = self._safe_error_detail(event)
                    self._last_error = detail
                    terminal_emitted = True
                    yield IntelligenceEvent(
                        event_type=IntelligenceEventType.ERROR,
                        detail=detail,
                        provider_response_id=response_id,
                    )
                    break

                if event_type == "response.incomplete":
                    response = getattr(event, "response", None)
                    response_id = getattr(response, "id", response_id)
                    detail = "OpenAI response ended incomplete"
                    self._last_error = detail
                    terminal_emitted = True
                    yield IntelligenceEvent(
                        event_type=IntelligenceEventType.DEGRADED,
                        detail=detail,
                        provider_response_id=response_id,
                        metadata=self._completion_metadata(response),
                    )
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

    async def cancel(self, request_id: str) -> None:
        active = self._active.get(request_id)
        if active is None:
            return
        active.token.cancel("cancel() requested")
        if active.stream is not None:
            await self._close_stream(active.stream)

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
