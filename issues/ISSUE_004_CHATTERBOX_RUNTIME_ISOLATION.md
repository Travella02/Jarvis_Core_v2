# ISSUE_004 — Chatterbox dependency pins conflict with modern GPU support

## Version / candidate

0.0.4 - Voice Lab

## Symptom

Installing `chatterbox-tts` directly into the Jarvis Core virtual environment would pull provider-specific PyTorch pins into Core. Upstream 0.1.7 pins Torch/Torchaudio 2.6 for Python 3.11, while RTX 50-series/Blackwell hardware requires a newer CUDA-capable PyTorch build.

## Expected behavior

Jarvis Core dependencies stay stable and provider-neutral. A TTS provider can be replaced without rewriting Core or poisoning the application's main Python environment.

## Final fix

Run Chatterbox as an isolated local sidecar in `.runtime/voice/chatterbox/.venv`. Core communicates through the `TextToSpeechProvider` adapter only. The setup script has an explicit `modern-cuda` compatibility profile; it does not silently modify the main `.venv`.

## Regression tests

Contract tests reject Chatterbox imports from `core/`, verify provider metadata through the neutral contract, and verify the runtime path remains under ignored `.runtime/`.

## Regression risk

Future Chatterbox releases may change their Python API or dependency constraints. The adapter/sidecar is the only code that should need updating.

## Technical lesson

Local-first does not mean dependency-coupled. Heavy ML runtimes should be isolated at the same provider boundary as cloud SDKs.
