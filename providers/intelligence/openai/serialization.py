"""OpenAI Responses API serialization helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from core.intelligence import IntelligenceContext, ReasoningPolicy
from core.tools import ToolDefinition
from providers.intelligence.openai.config import OpenAIProviderConfig


_REASONING_LEVELS = {
    "none": "none",
    "quick": "low",
    "low": "low",
    "standard": "medium",
    "medium": "medium",
    "high": "high",
    "xhigh": "xhigh",
    "extreme": "max",
    "max": "max",
}


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def serialize_messages(context: IntelligenceContext) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for index, raw in enumerate(context.messages):
        item = _plain(raw)
        if not isinstance(item, dict):
            raise ValueError(f"IntelligenceContext.messages[{index}] must be a mapping")
        role = item.get("role")
        if role not in {"developer", "system", "user", "assistant"}:
            raise ValueError(f"Unsupported message role at index {index}: {role!r}")
        if "content" not in item:
            raise ValueError(f"IntelligenceContext.messages[{index}] is missing content")
        messages.append(item)
    if not messages:
        raise ValueError("IntelligenceContext.messages must contain at least one message")
    return messages


def serialize_tools(tools: Sequence[ToolDefinition]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tool in tools:
        if tool.name in seen:
            raise ValueError(f"Duplicate tool name: {tool.name}")
        seen.add(tool.name)
        schema = _plain(tool.input_schema)
        if not schema:
            schema = {"type": "object", "properties": {}}
        if schema.get("type") != "object":
            raise ValueError(f"Tool {tool.name!r} input_schema must be a JSON object schema")
        result.append(
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": schema,
            }
        )
    return result


def reasoning_effort(policy: ReasoningPolicy, config: OpenAIProviderConfig) -> str:
    normalized = policy.level.strip().lower()
    if normalized == "auto":
        return config.reasoning_effort
    try:
        return _REASONING_LEVELS[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported reasoning level: {policy.level!r}") from exc


def parse_tool_arguments(value: str) -> dict[str, Any]:
    try:
        decoded = json.loads(value or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("Provider returned invalid JSON tool arguments") from exc
    if not isinstance(decoded, dict):
        raise ValueError("Provider tool arguments must decode to a JSON object")
    return decoded
