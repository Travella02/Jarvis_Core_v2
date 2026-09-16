# 0.0.2 - Intelligence Provider

## Delivered scope

- Real `OpenAIProvider` behind `IntelligenceProvider`.
- GPT-5.6 Luna (`gpt-5.6-luna`) as the initial development default.
- OpenAI Responses API streaming -> provider-neutral text/completion/error events.
- OpenAI function calls -> typed, non-executable `ToolRequest` objects.
- Cooperative foreground-stream cancellation and active-request tracking; no false claim of guaranteed remote inference cancellation.
- Provider-owned configuration for model, reasoning effort, timeout, output cap, API routing, and response storage.
- Luna capability/context metadata kept inside the provider.
- Provider-neutral behavioral benchmark harness with a V1 natural-language regression seed.
- Live development CLI for status, text streaming, and a tool-authority probe.
- OpenAI SDK direct-import regression guard.

## Deliberately not included

- ConversationContext/referent resolver/event bus (0.0.3).
- Audio, VAD, STT/TTS, interruption (0.0.4+).
- Stronger-model routing/usage budgets/provider fallback policy (0.0.6).
- Permission evaluation or any real tool executor (0.0.7).
- Memory, accounts/cloud authority, or desktop UI.

## Security/authority boundary

The model/provider receives tool descriptions only. A returned function call is represented as `ToolRequest` intent. 0.0.2 contains no execution callback in provider-visible tool metadata and no live tool executor in the intelligence lab or benchmark.

## Dependency

The candidate pins `openai==3.13.0`. Install/update with:

```powershell
python -m pip install -r requirements.txt
```
