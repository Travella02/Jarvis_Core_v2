# Testing Guide — 0.0.4 Repair37

Focused:
`python -m unittest tests.unit.test_repair37_luna_model_ab_probe -v`

Full:
`python -m unittest discover -s tests -v`

Clean GPT-5.6 Luna vs GPT-6 Luna A/B on Standard pricing:
`python -m apps.luna_model_ab_probe --rounds 10 --model-a gpt-5.6-luna --model-b gpt-6-luna --service-tier default`

Expected after each discarded model warmup:
- measured samples use continuation=yes
- reason=exact_chain
- reused=yes
- input_items=1

Use median TTFT as the primary latency comparison, with mean and p90 as supporting
evidence. Do not choose the production model from latency alone; compare quality
and cost separately.
