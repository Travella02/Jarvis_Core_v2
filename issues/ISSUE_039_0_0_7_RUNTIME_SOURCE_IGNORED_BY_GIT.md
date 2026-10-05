# ISSUE 039 — 0.0.7 runtime source package was ignored by Git

## Problem

The local working tree contained the complete `core/runtime/` source package,
but the clean 0.0.7 checkpoint did not. Git identified `.gitignore`'s bare
`runtime/` pattern as the reason `core/runtime/__init__.py` was ignored.

That creates a dangerous false-positive development state: Jarvis can work on
the developer machine while a clone, checkpoint, or final commit silently lacks
the runtime API source.

## V1 lesson reviewed

The V1 reference checkpoint used explicit generated-data ignores and did not
blanket-ignore every directory named `runtime`. Runtime implementation files
therefore remained source-controlled.

## Resolution

Repair2 anchors the generated directory rule to `/runtime/`, preserves the
`.runtime/` ignore, and adds a Git-aware regression test to ensure:

- `core/runtime/` remains source-controlled;
- root `runtime/` generated data remains ignored.

This is repository-integrity only; no runtime behavior changes.
