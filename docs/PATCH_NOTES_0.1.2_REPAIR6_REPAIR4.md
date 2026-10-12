# 0.1.2-repair6-repair4 — Mini vs full Realtime side-by-side benchmark

- **Confirmed official model IDs**: gpt-realtime-2.1-mini and gpt-realtime-2.1.
- **Controlled comparison**: `python scripts/realtime_ab.py mini` or `... full` runs the same desktop app using a process-only model override and disables the experimental parallel shadow probe. `.env` is untouched.
- **No behavioral changes**: the existing mandatory text-only routing gate, WebRTC media, local wake/sleep and permissions remain unchanged. This deliberately measures two models on the same *current safe architecture*. A future separate prototype is required for gate-free tool-first audio.
- **Terminal**: `[USER SPEECH]` / `[JARVIS REPLY]` identify speaker and Realtime model; `[Jarvis A/B Tool]` logs function invocations; `[Jarvis A/B Core]` reports the actual backend model chosen by Core; `[Jarvis A/B Usage]` reports billed token modalities, including cached input; `[Jarvis A/B Turn]` and `[Jarvis A/B Session]` aggregate usage, speech lengths, latency and estimated costs.
- **Pricing**: USD per million tokens as published October 9, 2026 at https://developers.openai.com/api/docs/pricing . Estimates compute uncached input and cached input independently. Unknown/missing breakdowns are **unpriced**, not invented. Core LLM costs, transcription costs, third-party tools and actual invoicing excluded.
- **Privacy**: transcripts print only to the dev terminal when tracing is enabled; no new file-based chat logs. Do not publish raw sensitive terminal data.
- **Tests**: 11 A/B unit tests, full Python suite 562 tests with 1 existing skip, diagnostics Status: ok, desktop static check passes; Electron/Vite launch and cloud comparisons must be performed on the user's Windows host.
- **V1 reference**: Existing Core-owned tool authority and response correlation are retained; no action executor moved into Realtime.
- **Live acceptance**: pending; leave patch artifacts in place and do not commit until accepted.
