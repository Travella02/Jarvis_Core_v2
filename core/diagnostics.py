"""Local-only Jarvis Core v2 diagnostics.

This module intentionally performs no network requests, provider calls, audio
capture, subprocess execution, filesystem mutation, or tool execution. Live
provider verification belongs to apps.intelligence_lab.
"""

from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
from typing import Any

from core.intelligence import IntelligenceProvider
from core.tools import ToolDefinition, ToolRequest, ToolResult
from core.voice import SpeechToTextProvider, TextToSpeechProvider, VoiceProfile


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
            "tool_contracts": [
                ToolDefinition.__name__,
                ToolRequest.__name__,
                ToolResult.__name__,
            ],
            "voice_contracts": [
                SpeechToTextProvider.__name__,
                TextToSpeechProvider.__name__,
                VoiceProfile.__name__,
            ],
        },
        "providers": {
            "intelligence": "provider-layer-ready",
            "stt": "not-configured",
            "tts": "not-configured",
        },
        "network_probe": "not-run",
        "external_actions": "disabled-in-core-diagnostics",
        "status": "ok",
    }


def _format_text(data: dict[str, Any]) -> str:
    providers = data["providers"]
    return "\n".join(
        [
            f"{data['project']} {data['version']} - Intelligence Provider diagnostics",
            f"Python: {data['python']}",
            "Contracts: intelligence=ready, tools=ready, voice=ready",
            (
                "Providers: "
                f"intelligence={providers['intelligence']}, "
                f"stt={providers['stt']}, tts={providers['tts']}"
            ),
            f"Network probe: {data['network_probe']}",
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
