"""Offline Repair12 A/B report. No API access; the input log stays on this computer.

Usage:
    python scripts/repair12_latency_report.py .runtime/repair12_baseline.log .runtime/repair12_decisions.log

Reports observed Mini speech->first-audio, and *hypothetical* router headroom.
This does NOT measure actual Decisions-authorized audio or claim a speedup.
"""
from __future__ import annotations

import re
import math
import statistics
import sys
from pathlib import Path


def _fields(line: str) -> dict[str, str]:
    return dict(re.findall(r'(?<!\S)([a-z_]+)=([^\s|]+)', line))


def _ms(value: str | None) -> int | None:
    if value is None: return None
    match = re.fullmatch(r'(\d+)(?:\s*ms)?', value.strip())
    return int(match.group(1)) if match else None


def parse_log(text: str) -> dict[int, dict]:
    turns: dict[int, dict] = {}
    for line in text.splitlines():
        if 'turn=' not in line: continue
        match = re.search(r'\bturn=(\d+)\b', line)
        if not match: continue
        turn = int(match.group(1))
        row = turns.setdefault(turn, {})
        if '[Jarvis Overlap]' in line:
            fields = _fields(line)
            if fields.get('phase') in {'direct', 'tool', 'sleep'}:
                row['route'] = fields['phase']
                row['mini_route_ms'] = _ms(fields.get('decision_ms'))
        elif '[Desktop latency]' in line:
            found = re.search(r'speech_end->first_audio=(\d+) ms', line)
            if found: row['first_audio_ms'] = int(found.group(1))
            found = re.search(r'speech_end->route=(\d+) ms', line)
            if found and row.get('mini_route_ms') is None: row['mini_route_ms'] = int(found.group(1))
        elif '[Jarvis Repair12 A/B]' in line:
            f = _fields(line)
            row['route'] = f.get('mini_route', row.get('route'))
            for key in ('mini_route_ms','first_audio_ms','decisions_ready_ms', 'potential_route_headroom_ms'):
                value = _ms(f.get(key))
                if value is not None: row[key] = value
            row['decisions_status'] = f.get('decisions_status')
            row['agreement'] = f.get('agreement')
            row['unsafe_direct'] = f.get('unsafe_direct')
        elif '[Jarvis Decisions Shadow]' in line and 'phase=compare' in line:
            f = _fields(line)
            row.setdefault('agreement', f.get('agreement'))
            row.setdefault('route', f.get('mini_route'))
    return turns


def _median(values: list[int]) -> int | None:
    return round(statistics.median(values)) if values else None


def _p90(values: list[int]) -> int | None:
    return sorted(values)[math.ceil(.9 * len(values)) - 1] if values else None


def compute_summary(turns: dict[int, dict], *, exclude_first: bool = True) -> dict[str, object]:
    # The very first turn generally contains a wake-and-command, not a fair
    # already-awake sample. Explicitly exclude it, even if its route is direct.
    first = min(turns) if turns else None
    eligible = [v for k,v in sorted(turns.items()) if not (exclude_first and k == first)
                and v.get('route') == 'direct' and v.get('first_audio_ms') is not None]
    first_audio = [x['first_audio_ms'] for x in eligible]
    mini_route = [x['mini_route_ms'] for x in eligible if x.get('mini_route_ms') is not None]
    headroom = [x['potential_route_headroom_ms'] for x in eligible if x.get('potential_route_headroom_ms') is not None]
    agreements = [x.get('agreement') for x in turns.values() if x.get('agreement') in {'yes','no'}]
    return {
        'direct_count': len(eligible),
        'median_first_audio_ms': _median(first_audio), 'p90_first_audio_ms': _p90(first_audio),
        'median_mini_route_ms': _median(mini_route),
        'median_potential_headroom_ms': _median(headroom),
        'decisions_agreements': agreements.count('yes'),
        'decisions_disagreements': agreements.count('no'),
        'shadow_observed_direct_count': sum(1 for x in eligible if x.get('decisions_status') == 'ok'),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print('Usage: python scripts/repair12_latency_report.py BASELINE_LOG SHADOW_LOG')
        return 2
    results = []
    for label, arg in [('BASELINE (Mini + real Core/Luna)',argv[1]),
                       ('DECISIONS SHADOW (Mini + real Core/Luna)',argv[2])]:
        path = Path(arg)
        if not path.is_file():
            print(f'File missing: {path}', file=sys.stderr); return 2
        summary = compute_summary(parse_log(path.read_text(encoding='utf-8',errors='replace')))
        results.append(summary)
        print(f'\n{label}')
        for k,v in summary.items(): print(f'  {k}: {v if v is not None else "not measured"}')
    before, after = results
    if before['median_first_audio_ms'] is not None and after['median_first_audio_ms'] is not None:
        print('\nObserved shadow-minus-baseline median first-audio difference: '
              f'{after["median_first_audio_ms"] - before["median_first_audio_ms"]:+d} ms')
    print('CAUTION: Decisions did NOT authorize audio in either arm; potential headroom is not speedup.')
    if min(before['direct_count'], after['direct_count']) < 20:
        print('PRELIMINARY: fewer than 20 already-awake direct turns per arm.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
