# ISSUE 055 — 0.1.1 short follow-ups still trigger long Realtime answers

## Status
Addressed by 0.1.1 Repair2; live acceptance required.

## Observed behavior
After Repair1, the user asked **“Why does that happen?”** and Realtime Mini still produced a paragraph-length explanation. An explicitly requested detailed answer was appropriately long, so the failure was not overall verbosity but insufficient distinction between ordinary conversational continuations and explicit depth requests.

## Root cause
The previous instruction (“usually one to three natural sentences”) was too soft. Realtime Mini could satisfy it with three long sentences and still add background/analogies. It also lacked a strong continuation rule telling it to answer only the missing point from existing context.

## Repair
- Default ordinary speech to one or two short sentences with a conversational word-range target.
- Treat short “why/how/what do you mean” turns as continuations and forbid restarting the prior explanation.
- Stop after the direct answer instead of adding unsolicited background, extra analogies, recaps, or related facts.
- Preserve personality explicitly.
- Allow explicit detailed/deep requests to expand naturally.

## Non-goal
Do not add a hard output-token cap. Hard clipping would damage natural speech, tool-result delivery, safety explanations, and user-requested detailed answers.
