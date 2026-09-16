"""Provider-neutral benchmark harness for Jarvis intelligence adapters.

0.0.2 seeds the harness and scoring mechanics. The corpus expands as the
conversation core, permissions, voice, and capability modules arrive.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.intelligence.contracts import (
    IntelligenceContext,
    IntelligenceEventType,
    IntelligenceProvider,
    ReasoningPolicy,
)
from core.tools import ToolDefinition


@dataclass(frozen=True, slots=True)
class BenchmarkExpectation:
    exact_text: str | None = None
    contains_text: str | None = None
    tool_name: str | None = None
    tool_arguments: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tool_arguments", MappingProxyType(dict(self.tool_arguments)))


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    prompt: str
    expectation: BenchmarkExpectation
    tools: tuple[ToolDefinition, ...] = ()
    reasoning_level: str = "standard"


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    case_id: str
    passed: bool
    text: str
    tool_requests: tuple[Mapping[str, Any], ...]
    failures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkRun:
    results: tuple[BenchmarkResult, ...]

    @property
    def passed(self) -> bool:
        return all(item.passed for item in self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for item in self.results if item.passed)


async def run_case(provider: IntelligenceProvider, case: BenchmarkCase) -> BenchmarkResult:
    trace = CorrelationContext(
        correlation_id=f"benchmark:{case.case_id}",
        request_id=f"benchmark:{case.case_id}",
        turn_id=case.case_id,
    )
    context = IntelligenceContext(
        trace=trace,
        messages=({"role": "user", "content": case.prompt},),
        metadata={"benchmark_case": case.case_id},
    )
    text_parts: list[str] = []
    tool_requests: list[Mapping[str, Any]] = []
    failures: list[str] = []

    async for event in provider.stream_response(
        context=context,
        tools=case.tools,
        reasoning_policy=ReasoningPolicy(level=case.reasoning_level, allow_escalation=False),
        cancellation_token=CancellationToken(),
    ):
        if event.event_type is IntelligenceEventType.TEXT_DELTA and event.text_delta:
            text_parts.append(event.text_delta)
        elif event.event_type is IntelligenceEventType.TOOL_REQUEST and event.tool_request:
            tool_requests.append(
                MappingProxyType(
                    {
                        "tool_name": event.tool_request.tool_name,
                        "operation": event.tool_request.operation,
                        "arguments": dict(event.tool_request.arguments),
                    }
                )
            )
        elif event.event_type in {
            IntelligenceEventType.ERROR,
            IntelligenceEventType.DEGRADED,
            IntelligenceEventType.CANCELLED,
        }:
            failures.append(event.detail or event.event_type.value)

    text = "".join(text_parts).strip()
    expectation = case.expectation
    if expectation.exact_text is not None and text != expectation.exact_text:
        failures.append(f"expected exact text {expectation.exact_text!r}, got {text!r}")
    if expectation.contains_text is not None and expectation.contains_text not in text:
        failures.append(f"expected text containing {expectation.contains_text!r}, got {text!r}")
    if expectation.tool_name is not None:
        matching = [item for item in tool_requests if item["tool_name"] == expectation.tool_name]
        if not matching:
            failures.append(f"expected tool request {expectation.tool_name!r}")
        elif expectation.tool_arguments and dict(matching[0]["arguments"]) != dict(expectation.tool_arguments):
            failures.append(
                f"expected tool arguments {dict(expectation.tool_arguments)!r}, "
                f"got {dict(matching[0]['arguments'])!r}"
            )

    return BenchmarkResult(
        case_id=case.case_id,
        passed=not failures,
        text=text,
        tool_requests=tuple(tool_requests),
        failures=tuple(failures),
    )


async def run_benchmark(
    provider: IntelligenceProvider,
    cases: Sequence[BenchmarkCase],
) -> BenchmarkRun:
    results = [await run_case(provider, case) for case in cases]
    return BenchmarkRun(results=tuple(results))


def load_cases(path: str | Path) -> tuple[BenchmarkCase, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    cases: list[BenchmarkCase] = []
    for raw in payload["cases"]:
        tools = tuple(
            ToolDefinition(
                name=item["name"],
                description=item["description"],
                input_schema=item.get("input_schema", {}),
            )
            for item in raw.get("tools", [])
        )
        expected = raw.get("expect", {})
        cases.append(
            BenchmarkCase(
                case_id=raw["id"],
                prompt=raw["prompt"],
                reasoning_level=raw.get("reasoning_level", "standard"),
                tools=tools,
                expectation=BenchmarkExpectation(
                    exact_text=expected.get("exact_text"),
                    contains_text=expected.get("contains_text"),
                    tool_name=expected.get("tool_name"),
                    tool_arguments=expected.get("tool_arguments", {}),
                ),
            )
        )
    return tuple(cases)
