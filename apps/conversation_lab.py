"""0.0.3 typed Conversation Core live lab."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from core.conversation import (
    ConversationContext,
    ConversationCore,
    Referent,
    ReferentKind,
    ReferentResolver,
)
from core.intelligence import ReasoningPolicy
from providers.intelligence.openai import OpenAIProvider, OpenAIProviderConfig


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def build_provider() -> OpenAIProvider:
    config = OpenAIProviderConfig.from_env(env_file=PROJECT_ROOT / ".env")
    return OpenAIProvider(config)


def build_core(provider: OpenAIProvider) -> ConversationCore:
    return ConversationCore(
        context=ConversationContext.create(
            user_id="local-development-user",
            speaker_id="typed-user",
            device_id="conversation-lab",
        ),
        provider=provider,
    )


def run_context_demo() -> int:
    context = ConversationContext.create(user_id="context-demo")
    media = Referent(
        "media-demo",
        ReferentKind.MEDIA,
        "YouTube video",
        source="media",
        supported_actions=frozenset({"pause", "resume"}),
    )
    task = Referent(
        "task-demo",
        ReferentKind.TASK,
        "calendar task",
        source="tasks",
        supported_actions=frozenset({"pause", "resume"}),
    )
    context.set_active_media(media)
    context.set_active_task(task, focus=True)
    resolver = ReferentResolver()
    focused = resolver.resolve(context, "it", action="resume")
    explicit = resolver.resolve(context, "the YouTube video", action="resume")

    print("Jarvis Core v2 0.0.3 - Conversation Context demo")
    print(
        "resume it -> "
        f"{focused.status.value}: {focused.referent.kind.value if focused.referent else 'none'} "
        f"({focused.referent.label if focused.referent else focused.reason})"
    )
    print(
        "resume the YouTube video -> "
        f"{explicit.status.value}: {explicit.referent.kind.value if explicit.referent else 'none'} "
        f"({explicit.referent.label if explicit.referent else explicit.reason})"
    )
    return 0 if focused.referent == task and explicit.referent == media else 1


def _print_context(core: ConversationCore) -> None:
    context = core.context
    payload = {
        "conversation_id": context.conversation_id,
        "state": core.state.state.value,
        "transcript_entries": len(context.recent_transcript),
        "current_focus": context.current_focus_entity.label if context.current_focus_entity else None,
        "last_discussed": context.last_discussed_entity.label if context.last_discussed_entity else None,
        "heard_response_state": context.heard_response_state.value,
        "active_cancellation_ids": list(core.cancellations.active_ids()),
    }
    print(json.dumps(payload, indent=2))


async def run_turn(core: ConversationCore, prompt: str, reasoning: str, number: int | None = None) -> int:
    if number is not None:
        print(f"Turn {number} user: {prompt}")
    result = await core.submit_typed(
        prompt,
        reasoning_policy=ReasoningPolicy(level=reasoning, allow_escalation=False),
    )
    label = f"Turn {number} Jarvis" if number is not None else "Jarvis"
    print(f"{label}: {result.text}")
    print(
        f"Status: {result.status} | turn={result.trace.turn_id} | "
        f"cancel={result.trace.cancellation_id} | core={core.state.state.value}"
    )
    return 0 if result.status == "completed" else 1


async def interactive(core: ConversationCore, reasoning: str) -> int:
    print("Jarvis Core v2 0.0.3 - Typed Conversation Lab")
    print("Commands: /context, /events, /quit")
    while True:
        try:
            prompt = input("You: ").strip()
        except EOFError:
            print()
            return 0
        if not prompt:
            continue
        if prompt in {"/quit", "/exit"}:
            return 0
        if prompt == "/context":
            _print_context(core)
            continue
        if prompt == "/events":
            for event in core.event_bus.history[-12:]:
                print(f"{event.timestamp.isoformat()} {event.event_type} [{event.origin}]")
            continue
        result = await core.submit_typed(
            prompt,
            reasoning_policy=ReasoningPolicy(level=reasoning, allow_escalation=False),
        )
        print(f"Jarvis: {result.text}")
        if result.status != "completed":
            print(f"Status: {result.status}: {result.detail or 'no detail'}")


async def _main_async(args: argparse.Namespace) -> int:
    if args.context_demo:
        return run_context_demo()
    provider = build_provider()
    health = await provider.health()
    if health.state.value == "not-configured":
        print(f"ERROR: {health.detail}", file=sys.stderr)
        return 2
    core = build_core(provider)
    prompts = list(args.turn or ())
    if args.prompt:
        prompts.append(args.prompt)
    if prompts:
        code = 0
        for number, prompt in enumerate(prompts, start=1):
            code = max(code, await run_turn(core, prompt, args.reasoning, number))
        _print_context(core)
        return code
    return await interactive(core, args.reasoning)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Jarvis Core v2 typed Conversation Core lab")
    parser.add_argument("--context-demo", action="store_true", help="run deterministic referent demo; no network")
    parser.add_argument("--prompt", help="send one typed turn through Conversation Core")
    parser.add_argument("--turn", action="append", help="send repeated turns through one shared context")
    parser.add_argument(
        "--reasoning",
        default="standard",
        choices=["none", "quick", "standard", "high", "extreme"],
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
