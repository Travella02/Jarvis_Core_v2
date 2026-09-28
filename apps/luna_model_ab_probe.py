"""Clean alternating A/B benchmark for Luna models through the real Conversation Core path."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, replace
from math import ceil
from statistics import mean, median
from time import monotonic
from typing import Any

from apps.voice_lab import PROJECT_ROOT
from core.conversation import ConversationContext, ConversationCore
from core.intelligence import ReasoningPolicy
from providers.intelligence.openai import OpenAIProvider, OpenAIProviderConfig


PROMPTS = (
    "Answer in one short sentence: what is gravity?",
    "Answer in one short sentence: why is the sky blue?",
    "Answer in one short sentence: what is a neutron star?",
    "Answer in one short sentence: why does sound not travel through empty space?",
    "Answer in one short sentence: what makes a joke funny?",
)


@dataclass(frozen=True)
class Sample:
    model: str
    round_index: int
    ttft_ms: float
    total_ms: float
    response_created_ms: float | None
    response_in_progress_ms: float | None
    provider_first_text_ms: float | None
    terminal_ms: float | None
    continuation: bool
    continuation_reason: str
    lane_committed: bool
    connection_reused: bool
    input_items: int | None
    actual_service_tier: str


def _fmt_ms(value: float | None) -> str:
    return "-" if value is None else f"{value:.0f}"


def _p90(values: list[float]) -> float:
    ordered = sorted(values)
    index = max(0, ceil(0.90 * len(ordered)) - 1)
    return ordered[index]


async def _core_sample(
    core: ConversationCore,
    provider: OpenAIProvider,
    model: str,
    prompt: str,
    round_index: int,
) -> Sample:
    started = monotonic()
    first_text_at: float | None = None

    def on_delta(_event) -> None:
        nonlocal first_text_at
        if first_text_at is None:
            first_text_at = monotonic()

    unsubscribe = core.event_bus.subscribe("response.text.delta", on_delta)
    try:
        result = await core.submit_voice(
            prompt,
            reasoning_policy=ReasoningPolicy(level="none", allow_escalation=False),
        )
    finally:
        unsubscribe()

    ended = monotonic()
    if result.status != "completed":
        raise RuntimeError(f"{model} round {round_index} ended with status={result.status}")
    if first_text_at is None:
        raise RuntimeError(f"{model} round {round_index} completed without a text delta")

    diag = provider.latest_request_diagnostics()
    return Sample(
        model=model,
        round_index=round_index,
        ttft_ms=(first_text_at - started) * 1000.0,
        total_ms=(ended - started) * 1000.0,
        response_created_ms=diag.get("response_created_ms"),
        response_in_progress_ms=diag.get("response_in_progress_ms"),
        provider_first_text_ms=diag.get("first_text_ms"),
        terminal_ms=diag.get("terminal_ms"),
        continuation=bool(diag.get("continuation")),
        continuation_reason=str(diag.get("continuation_reason") or "-"),
        lane_committed=bool(diag.get("lane_committed")),
        connection_reused=bool(diag.get("connection_reused")),
        input_items=diag.get("input_items"),
        actual_service_tier=str(diag.get("actual_service_tier") or "unknown"),
    )


def _make_stack(
    base: OpenAIProviderConfig,
    model: str,
    label: str,
) -> tuple[OpenAIProvider, ConversationCore]:
    config = replace(base, model=model)
    provider = OpenAIProvider(config)
    core = ConversationCore(
        context=ConversationContext.create(
            user_id="local-development-user",
            speaker_id=f"repair37-{label}",
            device_id="luna-model-ab-probe",
        ),
        provider=provider,
    )
    return provider, core


async def _warm(
    core: ConversationCore,
    provider: OpenAIProvider,
    model: str,
) -> None:
    sample = await _core_sample(
        core,
        provider,
        model,
        "Reply with exactly one word: Ready.",
        0,
    )
    print(
        f"Warmup {model}: TTFT={sample.ttft_ms:.0f} ms total={sample.total_ms:.0f} ms | "
        f"continuation={'yes' if sample.continuation else 'no'} "
        f"reason={sample.continuation_reason} "
        f"lane_committed={'yes' if sample.lane_committed else 'no'} "
        f"actual_tier={sample.actual_service_tier}"
    )


def _summary(model: str, samples: list[Sample]) -> None:
    ttft = [sample.ttft_ms for sample in samples]
    total = [sample.total_ms for sample in samples]
    provider_first = [
        sample.provider_first_text_ms
        for sample in samples
        if sample.provider_first_text_ms is not None
    ]

    print()
    print(f"{model} summary ({len(samples)} measured warm samples):")
    print(
        f"  Conversation Core TTFT: mean={mean(ttft):.0f} ms | "
        f"median={median(ttft):.0f} ms | p90={_p90(ttft):.0f} ms | "
        f"min={min(ttft):.0f} ms | max={max(ttft):.0f} ms"
    )
    print(
        f"  Conversation Core total: mean={mean(total):.0f} ms | "
        f"median={median(total):.0f} ms | p90={_p90(total):.0f} ms"
    )
    if provider_first:
        print(
            f"  Provider first text: mean={mean(provider_first):.0f} ms | "
            f"median={median(provider_first):.0f} ms | p90={_p90(provider_first):.0f} ms"
        )

    continuation_ok = sum(
        1 for sample in samples
        if sample.continuation
        and sample.continuation_reason == "exact_chain"
        and sample.lane_committed
        and sample.connection_reused
        and sample.input_items == 1
    )
    print(
        f"  Healthy continuation samples: {continuation_ok}/{len(samples)} "
        "(expected all measured samples)"
    )


async def run(args: argparse.Namespace) -> int:
    base = OpenAIProviderConfig.from_env(env_file=PROJECT_ROOT / ".env")
    base = replace(
        base,
        voice_transport="websocket",
        service_tier=args.service_tier,
    )

    provider_a, core_a = _make_stack(base, args.model_a, "a")
    provider_b, core_b = _make_stack(base, args.model_b, "b")

    samples: dict[str, list[Sample]] = {
        args.model_a: [],
        args.model_b: [],
    }

    print(
        "Repair37 Luna A/B | "
        f"model_a={args.model_a} | model_b={args.model_b} | "
        "reasoning=none | transport=websocket | "
        f"service_tier={args.service_tier} | rounds/model={args.rounds}"
    )
    print(
        "Only the real Conversation Core continuation path is measured. "
        "Each model has its own persistent WebSocket/session."
    )
    print("One warmup request per model is discarded before measurement.")

    try:
        await _warm(core_a, provider_a, args.model_a)
        await _warm(core_b, provider_b, args.model_b)

        stacks = {
            args.model_a: (provider_a, core_a),
            args.model_b: (provider_b, core_b),
        }

        for index in range(1, args.rounds + 1):
            prompt = PROMPTS[(index - 1) % len(PROMPTS)]
            order = (
                (args.model_a, args.model_b)
                if index % 2 == 1
                else (args.model_b, args.model_a)
            )
            print()
            print(f"Pair {index}/{args.rounds} | order: {order[0]} -> {order[1]}")

            for model in order:
                provider, core = stacks[model]
                sample = await _core_sample(core, provider, model, prompt, index)
                samples[model].append(sample)
                print(
                    f"  {model}: TTFT={sample.ttft_ms:.0f} ms "
                    f"total={sample.total_ms:.0f} ms | "
                    f"created={_fmt_ms(sample.response_created_ms)} "
                    f"in_progress={_fmt_ms(sample.response_in_progress_ms)} "
                    f"provider_first_text={_fmt_ms(sample.provider_first_text_ms)} "
                    f"terminal={_fmt_ms(sample.terminal_ms)} | "
                    f"continuation={'yes' if sample.continuation else 'no'} "
                    f"reason={sample.continuation_reason} "
                    f"reused={'yes' if sample.connection_reused else 'no'} "
                    f"input_items={sample.input_items} "
                    f"tier={sample.actual_service_tier}"
                )

        _summary(args.model_a, samples[args.model_a])
        _summary(args.model_b, samples[args.model_b])

        med_a = median([sample.ttft_ms for sample in samples[args.model_a]])
        med_b = median([sample.ttft_ms for sample in samples[args.model_b]])
        delta = med_b - med_a
        faster = args.model_a if delta > 0 else args.model_b
        magnitude = abs(delta)

        print()
        print(
            f"Median TTFT delta ({args.model_b} - {args.model_a}): {delta:+.0f} ms. "
            f"Lower-latency model in this run: {faster} by {magnitude:.0f} ms median."
        )
        print(
            "Treat this as latency evidence only. Model quality/cost should be evaluated "
            "separately before changing Jarvis production defaults."
        )
        return 0
    finally:
        await provider_a.close()
        await provider_b.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-a", default="gpt-5.6-luna")
    parser.add_argument("--model-b", default="gpt-6-luna")
    parser.add_argument(
        "--rounds",
        type=int,
        default=10,
        help="measured warm samples per model; one extra warmup/model is discarded",
    )
    parser.add_argument(
        "--service-tier",
        choices=["default", "auto", "fast", "priority"],
        default="default",
        help="use default for Standard pricing; Fast mode remains opt-in",
    )
    args = parser.parse_args(argv)

    if args.rounds < 2 or args.rounds > 30:
        parser.error("--rounds must be between 2 and 30")
    if args.model_a == args.model_b:
        parser.error("--model-a and --model-b must be different")

    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\nInterrupted")
        return 130
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
