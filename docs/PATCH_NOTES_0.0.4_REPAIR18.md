# 0.0.4-repair18 — Luna + Qwen Latency Pass

## Why

Live Qwen A/B testing showed Whisper was already fast and accurate after selecting the correct microphone endpoint. Warm Luna TTFT was still roughly 1.3–1.5 seconds, while Qwen often spent another 1.5–2.3 seconds producing a complete first waveform. The first Qwen turn also paid significant CUDA/inference warm-up.

## Changes

1. **Voice-only Luna output cap**
   - `JARVIS_OPENAI_VOICE_MAX_OUTPUT_TOKENS` defaults to 256.
   - General/non-voice `JARVIS_OPENAI_MAX_OUTPUT_TOKENS` remains 4096.

2. **GPT-5.6 prompt-cache policy**
   - Voice requests use implicit cache mode with a 30-minute TTL.
   - This is an optimization only; Conversation Core still owns the full authoritative history.

3. **Optional OpenAI service tier**
   - `JARVIS_OPENAI_SERVICE_TIER=auto` by default.
   - `fast`/`priority` are available for explicit latency/cost A/B testing.

4. **Real prewarm before listening**
   - Local TTS performs one hidden `Ready.` synthesis and discards the audio.
   - Luna performs one tiny hidden request and discards the response.
   - Neither warmup mutates ConversationContext.

5. **Qwen phrase generation budget**
   - Normal x-vector phrase synthesis drops from `max_new_tokens=8192` to 512.
   - The direct upstream diagnostic remains independent.

6. **Luna latency probe**
   - New `python -m apps.luna_latency_probe`.
   - Compares raw provider TTFT with Conversation Core TTFT using the same long-lived provider/client.
   - Supports an explicit `--service-tier fast` comparison.

## Explicit non-goal

Repair18 does **not** vendor or silently install a third-party Qwen streaming fork. The current accepted Qwen runtime returns full phrase waveforms; true incremental audio remains a future provider-runtime choice after separate evaluation.
