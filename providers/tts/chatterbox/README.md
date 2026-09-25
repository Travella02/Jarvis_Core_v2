# Chatterbox Turbo provider

0.0.4's first TTS candidate is local Chatterbox Turbo. It runs in an isolated
provider-specific Python environment and communicates with Jarvis through a
small JSON-line sidecar. Jarvis Core therefore does not inherit PyTorch,
Transformers, Diffusers, or Chatterbox dependency pins.

The provider supports a `VoiceProfile.reference_audio_path`, so the same neutral
profile contract can later back user-consented zero-shot voice cloning. 0.0.4
uses phrase streaming: Conversation Core deltas are chunked into natural phrases,
then each Chatterbox result is emitted as small PCM frames. Chatterbox's current
Python generation call is not itself sample-streaming; that distinction is
recorded rather than hidden.
