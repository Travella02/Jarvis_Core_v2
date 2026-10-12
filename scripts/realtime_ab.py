"""Run A/B sessions with process-local model selection (never edits .env).

Usage: python scripts/realtime_ab.py mini   or   python scripts/realtime_ab.py full
Stop desktop completely between runs. This launches `npm run desktop` once.
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

MODELS = {"mini": ("gpt-realtime-2.1-mini", False),
          "full": ("gpt-realtime-2.1", False),
          "mini-fast": ("gpt-realtime-2.1-mini", True),
          "full-fast": ("gpt-realtime-2.1", True),
          "mini-tools": ("gpt-realtime-2.1-mini", False),
          "full-tools": ("gpt-realtime-2.1", False),
          "mini-buffered": ("gpt-realtime-2.1-mini", False),
          "mini-overlap": ("gpt-realtime-2.1-mini", False)}

def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in MODELS:
        print("Usage: python scripts/realtime_ab.py mini|full|mini-fast|full-fast|mini-tools|full-tools|mini-buffered|mini-overlap", file=sys.stderr)
        return 2
    model, direct_only = MODELS[sys.argv[1]]
    env = os.environ.copy()
    tool_probe = sys.argv[1].endswith("-tools")
    env["JARVIS_REALTIME_MODEL"] = model
    env["JARVIS_REALTIME_TOOL_SELECTION_PROBE"] = "1" if tool_probe else "0"
    buffered_probe = sys.argv[1] == "mini-buffered"
    env["JARVIS_REALTIME_BUFFERED_TOOL_PROBE"] = "1" if buffered_probe else "0"
    overlap_probe = sys.argv[1] == "mini-overlap"
    env["JARVIS_REALTIME_OVERLAP_PROBE"] = "1" if overlap_probe else "0"
    env["JARVIS_PARALLEL_SHADOW_PROBE"] = "0"  # isolate models, avoid doubled costs
    env["JARVIS_REALTIME_DIRECT_ONLY_BENCHMARK"] = "1" if direct_only else "0"
    env["JARVIS_DESKTOP_CONVERSATION_TRACE"] = "1"
    print(f"[Jarvis A/B Launch] model={model} | "
          f"mode={'PARALLEL STREAM AUTHORIZATION - DRY RUN TOOLS' if overlap_probe else ('BUFFERED AUDIO - DRY RUN TOOLS' if buffered_probe else ('TEXT ONLY - TOOLS DRY RUN' if tool_probe else ('FAST DIRECT ONLY - NO TOOLS' if direct_only else 'SAFE ROUTED')))} | "
          "shadow=off | dev_transcripts=on", flush=True)
    root = Path(__file__).resolve().parents[1]
    try:
        return subprocess.call(["npm", "run", "desktop"], cwd=root, env=env, shell=(os.name == "nt"))
    except FileNotFoundError:
        print("npm not found in PATH", file=sys.stderr)
        return 127

if __name__ == "__main__":
    raise SystemExit(main())
