# OpenAIProvider

`OpenAIProvider` is the only package in 0.0.2 allowed to import or construct OpenAI SDK objects. Jarvis Core consumes the provider-neutral `IntelligenceProvider` contract.

The development default is `gpt-5.6-luna`. The model name, reasoning effort, timeout, and output cap are configuration owned by this provider and can be changed without changing core modules.

The provider uses the Responses API with streaming enabled and `store=False`. Tool/function calls are converted into non-executable `ToolRequest` objects. The provider never invokes a Jarvis tool.
