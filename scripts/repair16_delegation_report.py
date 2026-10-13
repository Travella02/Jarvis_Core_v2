"""Read-only, transcript-free summary of Repair16 Core/Luna acceptance logs.

Usage: python scripts/repair16_delegation_report.py path/to/repair16_live.log
This does not treat tool selection as completed Core work or silence as success.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import re
from statistics import median
from typing import Iterable

LUNA = re.compile(r"\[Jarvis Luna\] turn=(\d+) \| phase=([a-z_]+)")
TOOL = re.compile(r"\[Jarvis Tool Probe\] turn=(\d+) \| tool=([a-z_]+) \| phase=selection")
VOICE = re.compile(r"\[Jarvis Luna Voice\] turn=(\d+) \| phase=([a-z_]+)")
HOLD = re.compile(r"\[Jarvis Luna Cancel Test\] turn=(\d+) \| phase=([a-z_]+)")
OVERLAP = re.compile(r"\[Jarvis Overlap\] turn=(\d+) \| phase=([a-z_]+)")
KEY_VALUE = re.compile(r"(?:^|\|)\s*([a-z_]+)=([^|\r\n]+)")


def summarize(lines: Iterable[str]) -> dict:
    turns = defaultdict(lambda: {"tool": [], "core": [], "voice": [], "hold": [], "overlap": []})
    durations = []
    for line in lines:
        matches = [(LUNA.search(line), "core"), (TOOL.search(line), "tool"),
                   (VOICE.search(line), "voice"), (HOLD.search(line), "hold"),
                   (OVERLAP.search(line), "overlap")]
        for match, kind in matches:
            if not match:
                continue
            turn = int(match.group(1))
            turns[turn][kind].append(match.group(2))
            if kind == "core" and match.group(2) == "result":
                fields = dict((k, v.strip()) for k, v in KEY_VALUE.findall(line))
                try:
                    durations.append(int(fields["elapsed_ms"]))
                except (KeyError, ValueError):
                    pass
            break
    count = lambda kind, phase: sum(phase in record[kind] for record in turns.values())
    return {
        "observed_turns": len(turns),
        "luna_tool_selected": sum("ask_luna" in r["tool"] for r in turns.values()),
        "core_started": count("core", "core_started"),
        "core_results": count("core", "result"),
        "voice_started": count("voice", "started"),
        "voice_synthesis_completed": count("voice", "synthesis_completed"),
        "voice_text_fallback": count("voice", "text_fallback"),
        "action_tool_selected_dry_run": sum("test_action" in r["tool"] for r in turns.values()),
        "held_results": count("hold", "holding_result"),
        "held_result_discarded": count("hold", "stale_result_discarded"),
        "held_result_released": count("hold", "releasing_current_result"),
        "sleep_verified": count("overlap", "sleep"),
        "sleep_rejected": count("overlap", "sleep_rejected"),
        "median_core_result_elapsed_ms": median(durations) if durations else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="Captured console log (raw file remains local)")
    args = parser.parse_args()
    if not args.log.is_file():
        parser.error("log file does not exist")
    with args.log.open(encoding="utf-8", errors="replace") as f:
        result = summarize(f)
    print("Repair16 Core/Luna observability (no transcripts displayed)")
    for key, value in result.items():
        print(f"{key}={value if value is not None else 'n/a'}")
    if result["luna_tool_selected"] and not result["core_started"]:
        print("WARNING: Mini selected Luna, but no Core execution was observed.")
    if result["core_results"] and not result["voice_synthesis_completed"]:
        print("NOTE: Core results were observed without confirmed voice synthesis completion.")
    print("NOTE: Counts are observations, not proof of audible delivery or routing correctness.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
