"""Local-only Jarvis Core v2 diagnostics.

This module intentionally performs no network requests, provider/model loads,
audio capture, subprocess execution, filesystem mutation, or tool execution.
Live voice/provider verification belongs to development lab apps.
"""

from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
from typing import Any

from core.conversation import ConversationContext, ConversationCore, CoreStateMachine, EventBus, ReferentResolver
from core.intelligence import IntelligenceProvider
from core.tools import ToolDefinition, ToolRequest, ToolResult
from core.runtime import JarvisRuntime, RuntimeSettings, IntelligenceProviderRouter
from core.voice import (
    AudioInput,
    AudioOutput,
    EndpointDetector,
    SpeechTextChunker,
    SpeechToTextProvider,
    TextToSpeechProvider,
    VoiceLabEngine,
    VoiceLatencyTrace,
    VoiceProfile,
    VoiceProviderRegistry,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_version() -> str:
    return (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()


def collect_diagnostics() -> dict[str, Any]:
    return {
        "project": "Jarvis Core v2",
        "version": read_version(),
        "python": platform.python_version(),
        "foundation": {
            "intelligence_contract": IntelligenceProvider.__name__,
            "tool_contracts": [ToolDefinition.__name__, ToolRequest.__name__, ToolResult.__name__],
            "voice_contracts": [SpeechToTextProvider.__name__, TextToSpeechProvider.__name__, VoiceProfile.__name__],
        },
        "conversation": {
            "context": "ready" if ConversationContext else "missing",
            "referent_resolver": "ready" if ReferentResolver else "missing",
            "event_bus": "ready" if EventBus else "missing",
            "state_machine": "ready" if CoreStateMachine else "missing",
            "typed_path": "ready" if ConversationCore else "missing",
            "voice_path": "ready" if hasattr(ConversationCore, "submit_voice") else "missing",
            "persistence": "snapshot-contract-only",
        },
        "runtime": {
            "host": "ready" if JarvisRuntime else "missing",
            "settings": "ready" if RuntimeSettings else "missing",
            "provider_router": "ready" if IntelligenceProviderRouter else "missing",
            "event_replay": "sequence-cursor-ready",
            "durable_event_journal": "deferred",
        },
        "voice": {
            "engine": "ready" if VoiceLabEngine else "missing",
            "audio_contracts": "ready" if AudioInput and AudioOutput else "missing",
            "endpointing": "ready" if EndpointDetector else "missing",
            "tts_chunking": "ready" if SpeechTextChunker else "missing",
            "latency_telemetry": "ready" if VoiceLatencyTrace else "missing",
            "provider_registry": "ready" if VoiceProviderRegistry else "missing",
            "mode": "0.0.5-continuous-runtime-hosted",
            "full_duplex": "ready-headset-first",
        },
        "providers": {
            "intelligence": "provider-layer-ready",
            "stt_candidate": "whisper.cpp/large-v3-turbo-q5_0",
            "tts_candidate": "chatterbox/turbo-350m",
            "tts_ab_candidate": "qwen3-tts/12hz-0.6b-base",
            "runtime_probe": "not-run",
        },
        "network_probe": "not-run",
        "audio_probe": "not-run",
        "external_actions": "disabled-in-core-diagnostics",
        "status": "ok",
    }


def _format_text(data: dict[str, Any]) -> str:
    providers = data["providers"]
    conversation = data["conversation"]
    runtime = data["runtime"]
    voice = data["voice"]
    return "\n".join(
        [
            f"{data['project']} {data['version']} - Voice Lab diagnostics",
            f"Python: {data['python']}",
            "Contracts: intelligence=ready, tools=ready, voice=ready",
            (
                "Conversation: "
                f"context={conversation['context']}, referents={conversation['referent_resolver']}, "
                f"events={conversation['event_bus']}, state={conversation['state_machine']}, "
                f"typed={conversation['typed_path']}, voice={conversation['voice_path']}"
            ),
            (
                "Runtime: "
                f"host={runtime['host']}, settings={runtime['settings']}, "
                f"router={runtime['provider_router']}, replay={runtime['event_replay']}"
            ),
            (
                "Voice: "
                f"engine={voice['engine']}, audio={voice['audio_contracts']}, "
                f"endpointing={voice['endpointing']}, chunking={voice['tts_chunking']}, "
                f"telemetry={voice['latency_telemetry']}, mode={voice['mode']}"
            ),
            f"Candidates: STT={providers['stt_candidate']} | TTS={providers['tts_candidate']} | TTS A/B={providers['tts_ab_candidate']}",
            f"Runtime probe: {providers['runtime_probe']}",
            f"Network probe: {data['network_probe']} | Audio probe: {data['audio_probe']}",
            f"External actions: {data['external_actions']}",
            f"Status: {data['status']}",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Jarvis Core v2 local diagnostics")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)
    data = collect_diagnostics()
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(_format_text(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
