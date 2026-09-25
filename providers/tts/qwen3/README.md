# Qwen3-TTS provider candidate

Jarvis Core treats Qwen3-TTS as a replaceable local TTS adapter. The initial
candidate is `Qwen3-TTS-12Hz-0.6B-Base`, used for local voice cloning.

The provider runs in its own `.runtime/voice/qwen3_tts/.venv` and communicates
with Core through the existing `TextToSpeechProvider` contract. Core and
Conversation Core never import Qwen or PyTorch directly.

For the first A/B test we intentionally use the official Python package with
PyTorch CUDA and SDPA rather than adding another native runtime. If Qwen wins on
quality/latency, a later optimization can replace this adapter internals with a
native/quantized runtime without changing the provider contract.

Voice cloning needs a reference WAV. Supplying an exact reference transcript
uses Qwen's full ICL clone path; omitting it uses x-vector-only mode, which is
faster to set up but may reduce likeness.
