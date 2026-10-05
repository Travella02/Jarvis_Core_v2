"""Local 0.0.6 runtime/reconnect diagnostic.

No network, microphone, TTS, external tool, or credential is used.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import AsyncIterator, Sequence

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
from core.runtime import IntelligenceProviderRouter, JarvisRuntime, RuntimeSettings
from core.tools import ToolDefinition


class _DiagnosticProvider(IntelligenceProvider):
    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(provider="diagnostic", model="local-echo")

    async def stream_response(
        self,
        context: IntelligenceContext,
        tools: Sequence[ToolDefinition],
        reasoning_policy: ReasoningPolicy,
        cancellation_token: CancellationToken,
    ) -> AsyncIterator[IntelligenceEvent]:
        if cancellation_token.is_cancelled:
            yield IntelligenceEvent(event_type=IntelligenceEventType.CANCELLED)
            return
        yield IntelligenceEvent(event_type=IntelligenceEventType.TEXT_DELTA, text_delta="Runtime ready.")
        yield IntelligenceEvent(event_type=IntelligenceEventType.COMPLETED, provider_response_id="diag-response")

    def supports_tools(self) -> bool:
        return False

    def supports_vision(self) -> bool:
        return False

    def supports_reasoning_levels(self) -> bool:
        return False

    def context_limits(self) -> ContextLimits:
        return ContextLimits(max_input_tokens=4096, max_output_tokens=256)

    async def cancel(self, request_id: str) -> None:
        return None

    async def health(self) -> ProviderHealth:
        return ProviderHealth(ProviderHealthState.HEALTHY, "diagnostic provider ready")


def _snapshot_dict(runtime: JarvisRuntime) -> dict[str, object]:
    snap = runtime.snapshot()
    conversation = snap.conversation
    return {
        "runtime_id": snap.runtime_id,
        "version": snap.version,
        "lifecycle": snap.lifecycle.value,
        "health": snap.health.state.value,
        "event_cursor": snap.event_cursor,
        "oldest_event_sequence": snap.oldest_event_sequence,
        "settings": dict(snap.settings),
        "conversation": (
            {
                "conversation_id": conversation.conversation_id,
                "activity_state": conversation.activity_state,
                "presence_state": conversation.presence_state,
                "transcript_entries": conversation.transcript_entries,
                "active_turn_id": conversation.active_turn_id,
            }
            if conversation is not None
            else None
        ),
    }


async def run(*, emit_json: bool = False) -> int:
    settings = RuntimeSettings(event_history_limit=128)
    router = IntelligenceProviderRouter(default_route=settings.default_intelligence_route)
    router.register(settings.default_intelligence_route, _DiagnosticProvider(), make_default=True)
    runtime = JarvisRuntime(settings=settings, provider_router=router)
    runtime.start()
    try:
        core = runtime.create_conversation(
            user_id="runtime-lab-user",
            speaker_id="runtime-lab-speaker",
            device_id="runtime-lab",
        )
        await runtime.refresh_provider_health()
        reconnect_cursor = runtime.snapshot().event_cursor
        result = await core.submit_typed("runtime diagnostic")
        batch = runtime.events_after(reconnect_cursor)
        payload = {
            "snapshot": _snapshot_dict(runtime),
            "turn_status": result.status,
            "turn_text": result.text,
            "reconnect": {
                "after_sequence": reconnect_cursor,
                "event_count": len(batch.events),
                "gap_detected": batch.gap_detected,
                "event_types": [event.event_type for event in batch.events],
            },
            "trace_event_count": len(runtime.event_bus.events_for_correlation(result.trace.correlation_id)),
        }
        if emit_json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Jarvis Core v2 {payload['snapshot']['version']} - Runtime Lab")
            print(f"Lifecycle: {payload['snapshot']['lifecycle']} | Health: {payload['snapshot']['health']}")
            print(f"Conversation activity: {payload['snapshot']['conversation']['activity_state']}")
            print(f"Turn: {result.status} | {result.text}")
            print(
                "Reconnect: "
                f"cursor={reconnect_cursor} -> {batch.latest_sequence} | "
                f"events={len(batch.events)} | gap={'yes' if batch.gap_detected else 'no'}"
            )
            print(f"Trace events: {payload['trace_event_count']}")
            print("Status: ok")
        return 0
    finally:
        runtime.stop()
        runtime.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Jarvis Core v2 runtime foundation diagnostic")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)
    return asyncio.run(run(emit_json=args.json))


if __name__ == "__main__":
    raise SystemExit(main())
