# 0.0.4-repair20 live acceptance

1. Apply repair20 from the project root.
2. Run `python -m unittest discover -s tests -v`; expect 162 tests and `OK`.
3. Run `python -m apps.voice_benchmark`; expect 6/6.
4. Re-run the Qwen Voice Lab session used for repair19. Startup should pass `STT inference warmup completed...` instead of raising `NameError`.
5. Continue with the repair19 WebSocket-vs-HTTP latency A/B only after startup succeeds.
