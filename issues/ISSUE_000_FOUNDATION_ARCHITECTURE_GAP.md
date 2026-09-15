# ISSUE_000 — V2 had no testable architecture foundation

## Version / candidate

0.0.1 - Foundation

## Symptom

The newly initialized Jarvis Core v2 repository contained only the canonical handoff, V1 reference archive, local virtual environment, and Git metadata. There was no v2 source boundary, contract suite, diagnostic path, version marker, test structure, or issue discipline yet.

## Reproduction

Open the pre-0.0.1 repository and observe that no `VERSION`, `core/`, `providers/`, `tests/`, `issues/`, or executable v2 diagnostic path exists.

## Expected behavior

Before connecting a cloud model or implementing realtime voice, v2 needs mechanically testable boundaries that prevent provider/tool/voice coupling and preserve the V1 fallback as reference-only.

## Root cause

Intentional clean-rebuild starting state.

## Investigation

Reviewed the September 15, 2026 cloud-first master handoff and the supplied V1 0.3.6 clean checkpoint. The handoff explicitly assigns provider/tool/voice contracts and minimal diagnostics to 0.0.1, while Luna integration begins at 0.0.2 and voice runtime begins at 0.0.4.

## Attempted fixes

None before this candidate. Avoided prematurely adding the OpenAI SDK, audio libraries, Electron runtime, or V1 source.

## Final fix

Introduce only repository boundaries, standard-library contracts, diagnostics, documentation, and tests. Tool metadata is intentionally non-executable; intelligence and voice contracts contain no vendor SDK objects.

## Regression tests

Contract tests verify core source contains no OpenAI SDK imports, tool definitions expose no executor/callback, diagnostics are side-effect-free and report providers as not configured, required repository paths exist, and the candidate version is 0.0.1.

## Verification / live outcome

Automated verification is performed before patch delivery. Tanner live acceptance remains pending until the patch is applied and the testing guide is completed on the development machine.

## Regression risk

Low runtime risk because no production providers/tools/audio are connected. Primary risk is over-constraining later contracts; interfaces should evolve deliberately through normal versioned patches if real provider requirements reveal missing fields.

## Technical lesson

A clean rebuild benefits from making architectural boundaries executable before integrating the first vendor. This prevents early convenience choices from becoming hidden long-term coupling.
