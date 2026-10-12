#!/usr/bin/env python3
"""0.1.3 Decisions classifier evaluation: synthetic text, offline preview first.

One Decisions request (choice + two predicates) per case. Does NOT run Jarvis,
change speech, publish routing decisions, or execute a tool.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
from datetime import datetime
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from providers.intelligence.openai.config import merged_environment
from providers.intelligence.openai.decisions_shadow import (
    DECISIONS_ENDPOINT, DECISIONS_MODEL, INPUT_USD_PER_MILLION, QUESTION_SET, ROUTES,
    format_decisions_input,
)

# Expected routes are human-authored evaluation labels, not an oracle.
# A sample with ambiguous semantics should not be called an objective failure.
CASES = (
    ("mars", "Which planet is called the Red Planet?", "direct", "", ""),
    ("math", "What is 17 times 6?", "direct", "", ""),
    ("hello", "Hey, how are you Jarvis?", "direct", "", ""),
    ("thanks", "Thanks Jarvis.", "direct", "", ""),
    ("thanks_after_answer", "Thanks Jarvis!", "direct", "What is two plus two?", "Four."),
    ("thanks_followup", "Thanks, one more question: what is nine times eight?", "direct", "Hi there", "Hello!"),
    ("sleep_explicit", "Go to sleep, Jarvis.", "sleep", "", ""),
    ("sleep_thats_all", "Thanks Jarvis, that's all.", "sleep", "", ""),
    ("sleep_done", "That's everything for now, Jarvis.", "sleep", "", ""),
    ("sleep_bye", "I'm done for now. Talk to you later, Jarvis.", "sleep", "", ""),
    ("sleep_after_thanks", "Thanks Jarvis that's all.", "sleep", "What's 9 times 8?", "72."),
    ("sleep_single_thats_all", "That's all, Jarvis.", "sleep", "", ""),
    ("not_sleep_quote", "What does the phrase 'that's all' mean?", "direct", "", ""),
    ("not_sleep_problem", "Thanks, but I have another problem to solve.", "direct", "", ""),
    ("memory_pet", "What's my dog's name?", "memory", "", ""),
    ("memory_birthday", "Do you remember what I said my birthday was last month?", "memory", "", ""),
    ("memory_hobby", "Which hobby did I tell you I enjoyed?", "memory", "", ""),
    ("memory_visible", "What's my dog's name?", "direct", "My dog's name is Bella.", "You have a dog named Bella."),
    ("weather", "What's tomorrow's weather forecast?", "current_data", "", ""),
    ("news", "What's the latest news about OpenAI?", "current_data", "", ""),
    ("price", "What's the stock price of NVIDIA right now?", "current_data", "", ""),
    ("reasoning", "Compare three failure recovery strategies for a distributed exactly-once queue.", "ask_luna", "", ""),
    ("coding", "Design a robust multi-tenant permissions and audit architecture, including threat models.", "ask_luna", "", ""),
    ("action_open", "Open Calculator on my computer.", "action", "", ""),
    ("action_build", "Start building my app in the background.", "action", "", ""),
    ("action_schedule", "Schedule a reminder for me tomorrow at noon.", "action", "", ""),
    ("explain_vs_act", "Explain how to launch an application on Windows.", "direct", "", ""),
    ("uncertain_missing", "Do that one again.", "uncertain", "", ""),
    ("uncertain_other", "What about the other one?", "uncertain", "", ""),
    ("followup_with_context", "What about the first one?", "direct", "Two options are copper and silver.", "The first option is copper."),
)


def pct(values: list[float], percentile: float) -> float | None:
    if not values: return None
    sorted_values = sorted(values)
    position = (len(values)-1)*percentile/100
    lo = int(position)
    hi = min(len(sorted_values)-1, lo+1)
    return sorted_values[lo]+(sorted_values[hi]-sorted_values[lo])*(position-lo)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Synthetic Decisions API classification evaluation (no Jarvis changes)")
    parser.add_argument('--dry-run', action='store_true', help='Preview cases without billing')
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--timeout', type=float, default=7.0)
    parser.add_argument('--only', nargs='*', help='Case IDs to run')
    parser.add_argument('--output', type=Path, help='Optional output directory for CSV and summary JSON')
    args = parser.parse_args()
    if not 1 <= args.repeats <= 5 or not 1 <= args.timeout <= 60:
        parser.error('Requires 1-5 repeats and 1-60 second timeout')
    selected = [row for row in CASES if args.only is None or row[0] in args.only]
    if not selected:
        parser.error('No matching cases')
    print(f'Decisions 0.1.3 route-eval | {len(selected)} synthetic cases x {args.repeats} = {len(selected)*args.repeats} requests | shadow only')
    if args.dry_run:
        for cid, text, expected, *_ in selected:
            print(f'{cid:<23} expected={expected:<13} {text}')
        return 0
    api_key = merged_environment(PROJECT_ROOT / '.env').get('OPENAI_API_KEY')
    if not api_key:
        print('OPENAI_API_KEY missing; add it to project .env or process environment',file=sys.stderr)
        return 2
    output = args.output or PROJECT_ROOT / '.runtime' / f'decisions_eval_{datetime.now():%Y%m%d_%H%M%S}'
    if output.exists():
        parser.error(f'Output directory exists: {output}')
    output.mkdir(parents=True)
    rows=[]
    valid_routes={r[0] for r in ROUTES}
    async with httpx.AsyncClient(timeout=args.timeout) as client:
        for cid, utterance, expected, prior_user, prior_reply in selected:
            payload = {"model": DECISIONS_MODEL, "input": format_decisions_input(utterance, previous_user=prior_user, previous_reply=prior_reply), "questions": list(QUESTION_SET)}
            for repetition in range(1,args.repeats+1):
                outcome={'case':cid, 'repeat':repetition, 'expected':expected, 'route':None, 'confidence':None, 'sleep_probability':None, 'memory_probability':None, 'latency_ms':None, 'input_tokens':None, 'cost_usd':None, 'agreement':False, 'error':None}
                started=time.perf_counter()
                try:
                    response=await client.post(DECISIONS_ENDPOINT, headers={'Authorization':f'Bearer {api_key}', 'Content-Type':'application/json'},json=payload)
                    response.raise_for_status()
                    document=response.json()
                    answers=document.get('answers') or []
                    route=next((a for a in answers if isinstance(a,dict) and a.get('name')=='jarvis_route' and a.get('type')=='choice'),None)
                    if route is None or route.get('choice') not in valid_routes:
                        raise ValueError('missing_or_invalid_route')
                    outcome['route']=route['choice']
                    confidence=route.get('confidence')
                    if isinstance(confidence,(int,float)) and not isinstance(confidence,bool) and math.isfinite(float(confidence)):
                        outcome['confidence']=round(float(confidence),3)
                    for a in answers:
                        if not isinstance(a,dict) or a.get('type')!='predicate': continue
                        pr=a.get('probability')
                        if not isinstance(pr,(int,float)) or isinstance(pr,bool) or not math.isfinite(float(pr)):continue
                        if a.get('name')=='explicit_sleep_intent':outcome['sleep_probability']=round(float(pr),3)
                        if a.get('name')=='private_memory_required':outcome['memory_probability']=round(float(pr),3)
                    tokens=(document.get('usage') or {}).get('input_tokens')
                    if isinstance(tokens,int) and tokens >= 0:
                        outcome['input_tokens']=tokens
                        outcome['cost_usd']=tokens*INPUT_USD_PER_MILLION/1_000_000
                    outcome['agreement']=outcome['route']==expected
                except httpx.HTTPStatusError as exc:
                    outcome['error']=f'http_{exc.response.status_code}'
                except httpx.TimeoutException:
                    outcome['error']='timeout'
                except (httpx.RequestError, ValueError, KeyError, TypeError):
                    outcome['error']='unavailable'
                outcome['latency_ms']=round((time.perf_counter()-started)*1000,1)
                rows.append(outcome)
                print(f"[{cid:<23}] #{repetition} route={(outcome['route'] or 'error'):<13} expected={expected:<13} "
                      f"agree={'yes' if outcome['agreement'] else 'no '} confidence={outcome['confidence']} "
                      f"sleep_p={outcome['sleep_probability']} memory_p={outcome['memory_probability']} "
                      f"latency={outcome['latency_ms']}ms status={outcome['error'] or 'ok'}")
    with (output/'results.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0].keys()))
        writer.writeheader(); writer.writerows(rows)
    success=[r for r in rows if r['error'] is None]
    latencies=[r['latency_ms'] for r in success]
    summary={'successful':len(success),'total':len(rows),'agreement':round(sum(bool(x['agreement']) for x in success)/len(success),4) if success else None,
             'median_api_latency_ms':statistics.median(latencies) if latencies else None, 'p90_api_latency_ms':pct(latencies,90),
             'estimated_input_usd':sum(r['cost_usd'] or 0 for r in success),
             'notes':'Synthetic human labels; not calibrated accuracy. API call latency excludes speech transcription delay. No Jarvis routing was changed.'}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print('\n'+json.dumps(summary,indent=2))
    print('Results:', output)
    return 1 if len(success)!=len(rows) else 0

if __name__=='__main__':
    raise SystemExit(asyncio.run(main()))
