# OpenAIProvider

`OpenAIProvider` is the only package in 0.0.2 allowed to import or construct OpenAI SDK objects. Jarvis Core consumes the provider-neutral `IntelligenceProvider` contract.

The development default is `gpt-6-luna`. The model name, reasoning effort, timeout, and output cap are configuration owned by this provider and can be changed without changing core modules.

The provider uses the Responses API with streaming enabled and `store=False`. Tool/function calls are converted into non-executable `ToolRequest` objects. The provider never invokes a Jarvis tool.


Repair36 keeps the exact model ID under ORVEX control:
- `JARVIS_OPENAI_MODEL` selects the provider model without Core changes.
- Voice Lab can temporarily override it with `--luna-model`.
- The Luna latency probe can A/B exact IDs with `--model`.
- There is intentionally no blind automatic "latest" upgrade; newer Luna models are promoted only after ORVEX validates latency, behavior, and cost.

Standard processing is the provider default. Fast mode remains explicit opt-in.
