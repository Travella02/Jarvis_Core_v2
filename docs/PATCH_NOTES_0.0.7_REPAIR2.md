# Jarvis Core v2 0.0.7 Repair2 — Runtime source Git ignore scope

## Symptom

The local 0.0.7 working tree contains `core/runtime/`, but a clean Git-derived
checkpoint can omit that directory entirely. `git check-ignore -v` reports the
bare `.gitignore` rule `runtime/` as the match for files such as
`core/runtime/__init__.py`.

## Cause

A bare `runtime/` Git ignore pattern matches a directory with that name at any
depth, including the real Jarvis source package `core/runtime/`.

The generated root-level runtime directory and the source package are different
things and need different Git treatment.

## V1 lesson reviewed

The V1 reference checkpoint did not use a broad `runtime/` ignore rule. It
ignored explicit generated/runtime data locations instead, allowing runtime
source modules such as `jarvis/core/runtime.py` to remain versioned.

## Fix

- Replace the broad `runtime/` ignore rule with the root-anchored `/runtime/`.
- Keep `.runtime/` ignored.
- Add a regression test that verifies `core/runtime` is not ignored while a
  root `runtime/` directory remains ignored when Git metadata is available.

No Jarvis runtime API, voice, Luna, state, reconnect, protocol, or provider
behavior is changed by this repair.
