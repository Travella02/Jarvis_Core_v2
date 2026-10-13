"""Offline, transcript-free comparison of 0.1.4.1 Mini delegation A/B logs.

Run each 12-prompt sequence in exactly the order in TESTING_GUIDE_0.1.4.1.
The first *wake-only* utterance must be turn 1; the 12 questions are turns 2..13.
Repetitions / missed speech invalidate automatic per-prompt attribution. Inspect
terminal logs before interpreting the output as route accuracy.

Usage: python scripts/repair_0_1_4_1_routing_report.py baseline.log guided.log
No raw transcripts, credentials or response bodies are printed.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from statistics import median

# Expected classifications are human-reviewed TEST EXPECTATIONS, not ground truth
# labels from a model. The tool prints only numbers, never the user transcripts.
CASES = (
    ('greeting', 'direct'),
    ('simple_arithmetic', 'direct'),
    ('architecture_comparison', 'ask_luna'),
    ('simple_fact', 'direct'),
    ('memory_design', 'ask_luna'),
    ('simple_geography', 'direct'),
    ('multi_tenant_design', 'ask_luna'),
    ('short_definition', 'direct'),
    ('cancellation_race_design', 'ask_luna'),
    ('simple_arithmetic_2', 'direct'),
    ('job_recovery_design', 'ask_luna'),
    ('short_space_fact', 'direct'),
)
FIRST_QUESTION_TURN = 2
TOOL_LINE = re.compile(r'\[Jarvis Tool Probe\]\s+turn=(\d+)\s+\|\s+tool=([a-z_]+)\s+\|\s+phase=selection')
LATENCY_LINE = re.compile(r'\[Jarvis Latency Detail\]\s+turn=(\d+)\s+\|')
RESULT_LINE = re.compile(r'\[Jarvis Luna\]\s+turn=(\d+)\s+\|\s+phase=result\s+\|\s+status=([a-z_]+)')
FIELDS = ('route_ms', 'first_audio_ms')


def _value(line: str, name: str) -> int | None:
    match = re.search(r'\b' + name + r'=(\d+)\b', line)
    return int(match.group(1)) if match else None


def parse_log(lines: str) -> dict[int, dict]:
    """Summary only; never preserve or print spoken text."""
    rows: dict[int, dict] = {}
    for line in lines.splitlines():
        match = TOOL_LINE.search(line)
        if match:
            row = rows.setdefault(int(match.group(1)), {})
            row.setdefault('tools', set()).add('direct' if match.group(2) == 'none' else match.group(2))
            continue
        match = LATENCY_LINE.search(line)
        if match:
            row = rows.setdefault(int(match.group(1)), {})
            for name in FIELDS:
                value = _value(line, name)
                if value is not None:
                    row[name] = value
            continue
        match = RESULT_LINE.search(line)
        if match:
            rows.setdefault(int(match.group(1)), {})['core_result'] = match.group(2)
    return rows


def report(rows: dict[int, dict]) -> dict:
    entries = []
    correct = 0
    known = 0
    direct_audio = []
    direct_route = []
    core_completed = 0
    for index, (label, expected) in enumerate(CASES, start=FIRST_QUESTION_TURN):
        row = rows.get(index, {})
        tools = row.get('tools', set())
        actual = next(iter(tools)) if len(tools) == 1 else 'missing' if not tools else 'ambiguous'
        is_correct = actual == expected
        if actual not in {'missing', 'ambiguous'}:
            known += 1
            correct += int(is_correct)
        if actual == 'direct' and 'first_audio_ms' in row:
            direct_audio.append(row['first_audio_ms'])
            if 'route_ms' in row: direct_route.append(row['route_ms'])
        if actual == 'ask_luna' and row.get('core_result') == 'completed':
            core_completed += 1
        entries.append((index, label, expected, actual, row.get('core_result'), is_correct))
    extra_turns = sorted(t for t, row in rows.items() if 'tools' in row and t > len(CASES)+FIRST_QUESTION_TURN) # exclude sleep? recorded separately
    return {
        'cases': entries, 'known': known, 'correct': correct,
        'complete': known == len(CASES) and not extra_turns,
        'direct_audio_median_ms': round(median(direct_audio)) if direct_audio else None,
        'direct_audio_count': len(direct_audio),
        'direct_route_median_ms': round(median(direct_route)) if direct_route else None,
        'core_results_completed': core_completed,
        'extra_tool_turns': extra_turns,
    }


def format_report(name: str, data: dict) -> str:
    lines = [f'{name}: classified={data["known"]}/{len(CASES)} | matched_expectation={data["correct"]}/{data["known"]} (observed only)',
             f'  direct_first_audio_median_ms={data["direct_audio_median_ms"]} n={data["direct_audio_count"]}',
             f'  direct_route_median_ms={data["direct_route_median_ms"]}',
             f'  core_results_completed={data["core_results_completed"]}',
             f'  complete_sequence={data["complete"]}']
    for turn, label, expected, actual, core, success in data['cases']:
        lines.append(f'  turn={turn:02} {label}: expected={expected}, observed={actual}, '
                     f'core={core or "n/a"}, match={"yes" if success else "no"}')
    if data['extra_tool_turns']:
        lines.append('  WARNING: extra classified turns, sequence may be misaligned')
    if not data['complete']:
        lines.append('  WARNING: incomplete or extra turns; do NOT interpret accuracy as definitive')
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('guided', type=Path)
    args = parser.parse_args()
    for path in (args.baseline, args.guided):
        if not path.is_file(): parser.error(f'log not found: {path}')
    a, b = (report(parse_log(path.read_text(encoding='utf-8', errors='replace')))
            for path in (args.baseline, args.guided))
    print(format_report('Baseline', a))
    print(format_report('Guided', b))
    print('Reminder: expected route labels are test hypotheses; ASR errors/repeats can invalidate turn mapping.')
    print('Safety, correctness, cost, direct latency and actual Core completion all matter. This A/B does not establish causality.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
