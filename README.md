# Jarvis Core v2

Jarvis Core v2 is a clean rebuild of Jarvis with provider-independent intelligence, an ORVEX-owned realtime voice architecture, one authoritative conversation/context system, and tool authority kept outside model providers.

## Current milestone

**0.0.2 - Intelligence Provider**

This milestone connects the first real cloud intelligence implementation: `OpenAIProvider` behind the provider-neutral `IntelligenceProvider` contract, with GPT-5.6 Luna as the development default. It adds streaming text, function/tool-request translation, cooperative cancellation, provider-local configuration, and a provider-neutral benchmark harness.

It intentionally does **not** add the Conversation Core, voice runtime, permission engine, real tool execution, memory, UI, or stronger-model routing. Those remain later milestones.

## Requirements

- Python 3.11+
- Project-local `.venv` recommended
- OpenAI Python SDK 3.13.0 (declared in `pyproject.toml`)
- A development `OPENAI_API_KEY` for live provider tests only

## Install/update dependencies

```powershell
python -m pip install -r requirements.txt
```

## Local verification

```powershell
python -m unittest discover -s tests -v
python -m core.diagnostics
python -m apps.intelligence_lab --status
```

`--status` performs no network request and never prints the API key.

## Live provider probes

After creating a local `.env` from `.env.example` and setting `OPENAI_API_KEY`:

```powershell
python -m apps.intelligence_lab --prompt "Reply with exactly: Luna online."
python -m apps.intelligence_lab --tool-probe
python -m apps.intelligence_benchmark
```

The tool probe **does not execute a tool**. It verifies that a model/provider can emit a typed `ToolRequest` while authority remains outside the model.

## Canonical direction

The project-root master handoff PDF is canonical unless explicitly superseded. The V1 checkpoint under `Reference_jarvis_corev1/` is read-only behavior/code reference and must not be modified or used as the v2 foundation.
