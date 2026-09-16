"""Typed, non-executable tool contracts.

Intelligence providers may receive ToolDefinition metadata and may propose a
ToolRequest. They never receive an executor/callback. Permission evaluation,
confirmation, execution, verification, and auditing belong to Jarvis Core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from core.common.ids import CorrelationContext


class ToolResultStatus(str, Enum):
    SUCCEEDED = "succeeded"
    DENIED = "denied"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Provider-visible metadata for a tool operation family.

    No executable callable is allowed on this contract.
    """

    name: str
    description: str
    input_schema: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("ToolDefinition.name must be non-empty")
        object.__setattr__(self, "input_schema", _freeze_mapping(self.input_schema))


@dataclass(frozen=True, slots=True)
class ToolRequest:
    """A model/provider proposal for Jarvis Core to evaluate.

    This object represents intent, not authority. Receipt of a ToolRequest must
    never be interpreted as permission to execute it.
    """

    trace: CorrelationContext
    tool_name: str
    operation: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    provider_call_id: str | None = None
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        if not self.tool_name.strip():
            raise ValueError("ToolRequest.tool_name must be non-empty")
        if not self.operation.strip():
            raise ValueError("ToolRequest.operation must be non-empty")
        object.__setattr__(self, "arguments", _freeze_mapping(self.arguments))


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Provider-neutral result returned only after Jarvis Core handles authority."""

    trace: CorrelationContext
    tool_name: str
    operation: str
    status: ToolResultStatus
    output: Mapping[str, Any] = field(default_factory=dict)
    provider_call_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "output", _freeze_mapping(self.output))
