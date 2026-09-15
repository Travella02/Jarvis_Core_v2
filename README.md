# Jarvis Core v2

Jarvis Core v2 is a clean rebuild of Jarvis with provider-independent intelligence, an ORVEX-owned realtime voice architecture, one authoritative conversation/context system, and tool authority kept outside model providers.

## Current milestone

**0.0.1 - Foundation**

This milestone establishes repository boundaries, provider/tool/voice contracts, V1 reference documentation, issue discipline, and a local diagnostic path. It intentionally does **not** connect to GPT-5.6 Luna, microphone/audio devices, STT/TTS services, or real tools.

## Requirements

- Python 3.11+
- Project-local `.venv` recommended
- No runtime dependencies are required for 0.0.1

## Verify

```powershell
python -m unittest discover -s tests -v
python -m core.diagnostics
python -m core.diagnostics --json
```

The diagnostic path is local-only. In 0.0.1, intelligence, STT, and TTS providers must report as `not-configured`.

## Canonical direction

The project-root master handoff PDF is canonical unless explicitly superseded. The V1 checkpoint under `Reference_jarvis_corev1/` is read-only behavior/code reference and must not be modified or used as the v2 foundation.
