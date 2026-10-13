"""Repair13: compare real audible-turn timestamps, not hypothetical provider gains.

Usage: python scripts/repair13_latency_report.py baseline.log trim.log
The first turn of each run is excluded because it includes wake and warmup.
"""
from __future__ import annotations
import re
import statistics
import sys
from pathlib import Path

FIELDS = ('route_ms','pcm_ready_ms','gate_authorized_ms','pcm_signal_ms',
          'pcm_buffer_ready_ms','first_audio_ms','signal_to_first_audio_ms',
          'authorized_to_first_audio_ms')


def parse_log(text: str) -> dict[int, dict]:
    result: dict[int,dict] = {}
    for line in text.splitlines():
        if '[Jarvis Overlap]' in line and 'phase=direct ' in line:
            match = re.search(r'\bturn=(\d+)\b', line)
            if match: result.setdefault(int(match.group(1)), {})['direct'] = True
        if '[Jarvis Latency Detail]' not in line:
            continue
        match = re.search(r'\bturn=(\d+)\b', line)
        if not match: continue
        turn = int(match.group(1))
        row = result.setdefault(turn, {})
        for field in FIELDS:
            value = re.search(r'\b'+field+r'=([^ |]+)',line)
            if value:
                try: row[field] = int(value.group(1))
                except ValueError: pass
        flag = re.search(r'\bpcm_trim_enabled=(true|false)\b',line,re.I)
        if flag: row['trim'] = flag.group(1).lower()=='true'
    return result


def _quantile(values: list[int], fraction: float) -> int | None:
    if not values: return None
    ordered = sorted(values)
    return ordered[max(0,min(len(ordered)-1,int((len(ordered)-1)*fraction+0.5)))]


def summary(rows: dict[int,dict], exclude_first: bool = True) -> dict:
    first = min(rows) if rows else 0
    direct = [row for turn,row in sorted(rows.items()) if row.get('direct')
              and 'first_audio_ms' in row and (not exclude_first or turn!=first)]
    outcome = {'n':len(direct)}
    for field in FIELDS:
        observations = [row[field] for row in direct if field in row]
        outcome[field+'_n'] = len(observations)
        outcome[field+'_median'] = round(statistics.median(observations)) if observations else None
        if field == 'first_audio_ms':
            outcome['first_audio_p90'] = _quantile(observations,.9)
    return outcome


def main(argv: list[str]) -> int:
    if len(argv)!=3:
        print('Usage: python scripts/repair13_latency_report.py baseline.log trim.log',file=sys.stderr)
        return 2
    baseline, trim = (summary(parse_log(Path(path).read_text(encoding='utf-8',errors='replace')))
                      for path in argv[1:])
    for label, report in [('Original PCM',baseline),('Leading-silence trim',trim)]:
        print(f'\n{label} | observed already-awake direct turns: {report["n"]}')
        for key in ('first_audio_ms','route_ms','pcm_signal_ms','pcm_buffer_ready_ms',
                    'gate_authorized_ms','authorized_to_first_audio_ms','signal_to_first_audio_ms'):
            print(f'  {key}: median={report[key+"_median"]} ms (n={report[key+"_n"]})')
        print(f'  first_audio_p90: {report["first_audio_p90"]} ms')
    a,b=baseline.get('first_audio_ms_median'),trim.get('first_audio_ms_median')
    if a is not None and b is not None:
        print(f'\nObserved first-audio median change: {a-b:+} ms (positive = trim was faster).')
    print('A/B is observational and noisy, not proof of production gain. Compare 20+ already-awake turns per arm.')
    return 0

if __name__=='__main__':raise SystemExit(main(sys.argv))
