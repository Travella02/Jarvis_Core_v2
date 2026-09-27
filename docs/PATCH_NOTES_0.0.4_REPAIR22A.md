# 0.0.4 Repair22a — Qwen streaming candidate attention fallback

Repair22's isolated streaming candidate reached model loading, but Transformers attempted to use FlashAttention 2 after the incompatible Windows FlashAttention package was removed.

Repair22a makes one surgical experimental change: it adds `attn_implementation="sdpa"` to the existing candidate worker's `Qwen3TTSModel.from_pretrained(...)` call. The installer preserves every other Repair22 argument and behavior.

The accepted Repair20 Qwen provider/runtime is untouched. The installer backs up the candidate worker before editing it and verifies the SDPA change afterward.
