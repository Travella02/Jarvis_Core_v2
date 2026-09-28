"""Live Luna TTFT/model-continuation probe for Jarvis Voice Lab latency work."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
from statistics import mean
from time import monotonic

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.conversation import ConversationContext, ConversationCore
from core.conversation.engine import VOICE_RESPONSE_INSTRUCTION
from core.intelligence import IntelligenceContext, IntelligenceEventType, ReasoningPolicy
from providers.intelligence.openai import OpenAIProvider, OpenAIProviderConfig
from apps.voice_lab import PROJECT_ROOT


PROMPT = "Reply with exactly one word: Ready."


async def _raw_once(provider: OpenAIProvider, number: int) -> tuple[float, float]:
    context = IntelligenceContext(
        trace=CorrelationContext.create(),
        messages=(
            {"role": "developer", "content": VOICE_RESPONSE_INSTRUCTION},
            {"role": "user", "content": PROMPT},
        ),
        metadata={"input_channel": "voice", "conversation_id": f"raw-latency-{number}"},
    )
    started = monotonic()
    first = None
    async for event in provider.stream_response(
        context, (), ReasoningPolicy(level="none", allow_escalation=False), CancellationToken()
    ):
        if event.event_type is IntelligenceEventType.TEXT_DELTA and first is None:
            first = monotonic()
    ended = monotonic()
    if first is None:
        raise RuntimeError("raw Luna probe completed without a text delta")
    return (first - started) * 1000.0, (ended - started) * 1000.0


async def _core_once(core: ConversationCore) -> tuple[float, float]:
    started = monotonic()
    first = None

    def on_delta(_event) -> None:
        nonlocal first
        if first is None:
            first = monotonic()

    unsubscribe = core.event_bus.subscribe("response.text.delta", on_delta)
    try:
        result = await core.submit_voice(
            PROMPT,
            reasoning_policy=ReasoningPolicy(level="none", allow_escalation=False),
        )
    finally:
        unsubscribe()
    ended = monotonic()
    if result.status != "completed":
        raise RuntimeError(f"Conversation Core probe ended with status={result.status}")
    if first is None:
        raise RuntimeError("Conversation Core probe completed without a text delta")
    return (first - started) * 1000.0, (ended - started) * 1000.0


async def run(args: argparse.Namespace) -> int:
    config = OpenAIProviderConfig.from_env(env_file=PROJECT_ROOT / ".env")
    updates = {"voice_transport": args.transport}
    if args.model is not None:
        updates["model"] = args.model
    if args.service_tier is not None:
        updates["service_tier"] = args.service_tier
    config = replace(config, **updates)
    provider = OpenAIProvider(config)
    core = ConversationCore(
        context=ConversationContext.create(
            user_id="local-development-user",
            speaker_id="luna-latency-probe",
            device_id="voice-lab",
        ),
        provider=provider,
    )

    print(
        f"Luna latency probe | model={config.model} | reasoning=none | "
        f"transport={config.voice_transport} | "
        f"voice_max_output_tokens={config.voice_max_output_tokens} | service_tier={config.service_tier}"
    )
    print("This makes tiny live API requests; no microphone or TTS is used.")

    raw: list[float] = []
    core_times: list[float] = []
    for index in range(1, args.rounds + 1):
        raw_ttft, raw_total = await _raw_once(provider, index)
        core_ttft, core_total = await _core_once(core)
        raw.append(raw_ttft)
        core_times.append(core_ttft)
        diag = provider.latest_request_diagnostics()
        cont = "yes" if diag.get("continuation") else "no"
        reason = diag.get("continuation_reason") or "-"
        committed = "yes" if diag.get("lane_committed") else "no"
        actual_tier = diag.get("actual_service_tier") or "unknown"
        print(
            f"Round {index}: raw provider TTFT={raw_ttft:.0f} ms total={raw_total:.0f} ms | "
            f"Conversation Core TTFT={core_ttft:.0f} ms total={core_total:.0f} ms | "
            f"core continuation={cont} reason={reason} lane_committed={committed} "
            f"actual_tier={actual_tier}"
        )

    def warm(values: list[float]) -> list[float]:
        return values[1:] if len(values) > 1 else values

    raw_warm = warm(raw)
    core_warm = warm(core_times)
    print("Summary (excluding round 1 when multiple rounds are available):")
    print(f"  raw Luna TTFT average: {mean(raw_warm):.0f} ms")
    print(f"  Conversation Core TTFT average: {mean(core_warm):.0f} ms")
    print(f"  apparent Core/app overhead: {max(0.0, mean(core_warm) - mean(raw_warm)):.0f} ms")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument(
        "--model",
        default=None,
        help=(
            "Repair36: exact Luna/OpenAI model ID for this probe. "
            "Omit to use JARVIS_OPENAI_MODEL / provider default."
        ),
    )
    parser.add_argument(
        "--transport",
        choices=["websocket", "http"],
        default="websocket",
        help="match Voice Lab transport explicitly; websocket is the voice default",
    )
    parser.add_argument(
        "--service-tier",
        choices=["auto", "default", "fast", "priority"],
        default=None,
        help="override JARVIS_OPENAI_SERVICE_TIER for this probe only",
    )
    args = parser.parse_args(argv)
    if args.rounds < 1 or args.rounds > 10:
        parser.error("--rounds must be between 1 and 10")
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
