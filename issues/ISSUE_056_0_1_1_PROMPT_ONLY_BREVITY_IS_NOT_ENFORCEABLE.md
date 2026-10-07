# ISSUE 056 — Prompt-only brevity is not enforceable

## Problem
Realtime Mini continued producing long paragraph answers to ordinary follow-up questions even after two progressively stronger prompt-only brevity repairs.

## Decision
Prompt guidance remains useful for conversational shape and personality, but normal spoken responses now also have a structural provider output ceiling. Explicit requests for depth use a narrow local expansion tool to grant a larger budget for that response only.

## Architecture
Jarvis personality is moved into a provider-neutral Core conversation module so future conversational frontends can inherit the same identity. Provider-specific code owns only Realtime transport/tool/budget mechanics.

## Guardrail
The normal token ceiling also applies to tool-call generation, so delegation acceptance remains part of live regression. If complex delegated constraints prove too large for this ceiling, the correct fix is a separate tool-call budget path—not weakening ordinary conversational brevity again.
