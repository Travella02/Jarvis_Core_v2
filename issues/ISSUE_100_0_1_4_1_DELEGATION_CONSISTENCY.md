# ISSUE-100 — Decision consistency / avoid Mini truncation from misrouting

Observed in 0.1.3: Mini appropriately used ask_luna for complex architecture and memory questions, but answered another multi-constraint architecture comparison directly. The direct response exceeded combined 1,024-token text/audio output. Repair14 compact router was rejected because it sometimes omitted the required marker and was slower.

0.1.4.1 hypothesis: a slightly more discriminating rubric in the existing single Mini routing call may improve choices without creating an extra API call. Long instructions may also slow ordinary routing; A/B baseline preserves the accepted path, and the new arm must earn acceptance through actual user tests. No retrospective claims without measured data.

Out of scope: adaptive response token continuation, model switch, personality, phonetic wake recognition, web/current data, memory tools or external actions. All action permissions remain with Core.

Acceptance evidence: 12-turn labeled observations for both modes, correct Core completion, direct response latency, no wake/sleep or speech quality regressions; >20 direct turns per arm recommended for latency significance.
