# ISSUE 009 - Chatterbox Model Asset Delivery

## Trigger

0.0.4-repair3 proved the Blackwell runtime itself is healthy (`torch=2.7.1+cu128`, CUDA smoke test passed), but `ChatterboxTurboTTS.from_pretrained()` failed while Hugging Face was downloading the Turbo snapshot with Windows `WinError 10054` (remote host forcibly closed the connection).

## Architectural risk

A TTS provider must not make first model startup depend on a fragile opaque download inside the provider library. That also makes installation progress, retry/resume behavior, integrity checks, storage accounting, and offline startup difficult for ORVEX to own.

## Repair decision

- ORVEX setup owns the Chatterbox Turbo model asset installation.
- Only the files used by the Turbo inference path are fetched, rather than the full repository snapshot.
- Large model weights use resumable `curl.exe` retries with BITS fallback and SHA-256 verification before atomic promotion.
- The Chatterbox sidecar receives an explicit provider-local model directory and calls `from_local()`.
- Provider startup performs no model download/network request after setup succeeds.
- The model directory remains under ignored `.runtime/voice/chatterbox/` and is replaceable by configuration.

## Boundary

This does not make Chatterbox permanent. The model directory, runtime, and adapter remain provider-owned and can be replaced without changing Voice Core, Conversation Core, or Luna integration.
