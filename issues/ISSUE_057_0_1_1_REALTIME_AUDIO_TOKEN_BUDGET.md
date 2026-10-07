# ISSUE 057 — Realtime audio token budget was sized like text

## Problem
Repair3 set `max_output_tokens=80` based on a text-token intuition. Realtime audio responses count both text and audio output tokens, and assistant audio is approximately one audio token per 50 ms. An 80-token ceiling can therefore cut normal spoken answers after only a few seconds.

## Resolution
Use 320 tokens as the ordinary response ceiling and 1024 for an explicitly expanded response. The prompt still targets concise 20–45 word ordinary answers; the token limit is a runaway guard, not a word-count control. Desktop telemetry now prints text/audio output-token details so the budget can be tuned empirically.

## Architecture rule
Do not infer spoken word count directly from Realtime `max_output_tokens`. Keep response style policy separate from transport/model token guardrails.
