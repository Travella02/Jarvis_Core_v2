"""0.0.2 live intelligence lab.

This is a development probe, not the final Jarvis conversation UI. It proves
that the real cloud provider can stream text and propose tool calls while tool
authority remains outside the model/provider.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import uuid4

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.intelligence import IntelligenceContext, IntelligenceEventType, ReasoningPolicy
from core.tools import ToolDefinition
from providers.intelligence.openai import OpenAIProvider, OpenAIProviderConfig


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def build_provider() -> OpenAIProvider:
    config = OpenAIProviderConfig.from_env(env_file=PROJECT_ROOT / ".env")
    return OpenAIProvider(config)


def build_context(prompt: str) -> IntelligenceContext:
    request_id = f"lab-{uuid4().hex}"
    return IntelligenceContext(
        trace=CorrelationContext(
            correlation_id=request_id,
            request_id=request_id,
            turn_id=request_id,
        ),
        messages=({"role": "user", "content": prompt},),
        metadata={"source": "0.0.2-intelligence-lab"},
    )


async def status(provider: OpenAIProvider) -> int:
    health = await provider.health()
    limits = provider.context_limits()
    metadata = provider.metadata
    print("Jarvis Core v2 0.0.2 - Intelligence Provider")
    print(f"Provider: {metadata.provider}")
    print(f"Model: {metadata.model}")
    print(f"Health: {health.state.value}")
    print(f"Detail: {health.detail or 'none'}")
    print(f"Tools: {'yes' if provider.supports_tools() else 'no'}")
    print(f"Vision: {'yes' if provider.supports_vision() else 'no'}")
    print(f"Reasoning levels: {'yes' if provider.supports_reasoning_levels() else 'no'}")
    print(f"Context limit: {limits.max_input_tokens or 'unknown'}")
    print(f"Max model output: {limits.max_output_tokens or 'unknown'}")
    print(f"Configured request output cap: {provider.config.max_output_tokens}")
    print("Network probe: not run")
    return 0


async def run_prompt(provider: OpenAIProvider, prompt: str, reasoning: str) -> int:
    context = build_context(prompt)
    token = CancellationToken()
    terminal = None
    print(f"[{provider.metadata.provider}/{provider.metadata.model}] ", end="", flush=True)
    async for event in provider.stream_response(
        context=context,
        tools=(),
        reasoning_policy=ReasoningPolicy(level=reasoning, allow_escalation=False),
        cancellation_token=token,
    ):
        if event.event_type is IntelligenceEventType.TEXT_DELTA and event.text_delta:
            print(event.text_delta, end="", flush=True)
        elif event.event_type in {
            IntelligenceEventType.ERROR,
            IntelligenceEventType.DEGRADED,
            IntelligenceEventType.CANCELLED,
        }:
            terminal = event
        elif event.event_type is IntelligenceEventType.COMPLETED:
            terminal = event
    print()
    if terminal and terminal.event_type in {
        IntelligenceEventType.ERROR,
        IntelligenceEventType.DEGRADED,
        IntelligenceEventType.CANCELLED,
    }:
        print(f"Status: {terminal.event_type.value}: {terminal.detail}")
        return 1
    print("Status: completed")
    return 0


async def run_tool_probe(provider: OpenAIProvider, reasoning: str) -> int:
    tool = ToolDefinition(
        name="jarvis_test_probe",
        description=(
            "Development-only provider boundary probe. Use this function when explicitly asked "
            "to run the Jarvis provider tool probe."
        ),
        input_schema={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
    )
    prompt = (
        "Run the Jarvis provider tool probe now. Call jarvis_test_probe exactly once with "
        "value='provider-boundary-ok'. Do not claim the tool has executed; only request it."
    )
    context = build_context(prompt)
    tool_requests = []
    failures = []
    async for event in provider.stream_response(
        context=context,
        tools=(tool,),
        reasoning_policy=ReasoningPolicy(level=reasoning, allow_escalation=False),
        cancellation_token=CancellationToken(),
    ):
        if event.event_type is IntelligenceEventType.TOOL_REQUEST and event.tool_request:
            tool_requests.append(event.tool_request)
        elif event.event_type in {IntelligenceEventType.ERROR, IntelligenceEventType.DEGRADED}:
            failures.append(event.detail or event.event_type.value)

    if failures:
        print(f"Tool probe failed: {failures[0]}")
        return 1
    if len(tool_requests) != 1:
        print(f"Tool probe failed: expected exactly 1 ToolRequest, got {len(tool_requests)}")
        return 1
    request = tool_requests[0]
    if request.tool_name != "jarvis_test_probe" or dict(request.arguments) != {
        "value": "provider-boundary-ok"
    }:
        print(
            "Tool probe failed: unexpected request "
            f"{request.tool_name} {dict(request.arguments)!r}"
        )
        return 1

    print("ToolRequest received: jarvis_test_probe(value='provider-boundary-ok')")
    print("Execution: BLOCKED BY DESIGN - provider emitted intent only; no tool executor was called")
    print("Status: completed")
    return 0


async def _main_async(args: argparse.Namespace) -> int:
    provider = build_provider()
    if args.status:
        return await status(provider)
    if args.tool_probe:
        return await run_tool_probe(provider, args.reasoning)
    prompt = args.prompt
    if prompt is None:
        if not sys.stdin.isatty():
            prompt = sys.stdin.read().strip()
        else:
            prompt = input("Prompt: ").strip()
    if not prompt:
        print("ERROR: prompt cannot be empty", file=sys.stderr)
        return 2
    return await run_prompt(provider, prompt, args.reasoning)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Jarvis Core v2 OpenAI intelligence lab")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="show local provider configuration only")
    mode.add_argument("--tool-probe", action="store_true", help="run a live non-executing tool-call probe")
    parser.add_argument("--prompt", help="send one live prompt through IntelligenceProvider")
    parser.add_argument(
        "--reasoning",
        default="standard",
        choices=["none", "quick", "standard", "high", "extreme"],
        help="provider-neutral reasoning level for this probe",
    )
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_main_async(args))
    except KeyboardInterrupt:
        print("\nCancelled")
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
