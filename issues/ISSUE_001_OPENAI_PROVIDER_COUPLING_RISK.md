# ISSUE_001 — OpenAI provider coupling risk

## Version / candidate

0.0.2 - Intelligence Provider

## Symptom

The first real cloud intelligence implementation requires an OpenAI SDK, provider-specific streaming events, function-call schemas, model IDs, and reasoning values. If those details leak into Core, Jarvis becomes OpenAI/Luna-specific and future provider replacement requires a rewrite.

## Reproduction

A naive implementation imports the OpenAI SDK from conversation/core modules or passes OpenAI response/function objects across the `IntelligenceProvider` boundary.

## Expected behavior

Only the OpenAI adapter package knows OpenAI SDK/API objects. Core receives serializable context and emits/consumes provider-neutral `IntelligenceEvent`, `ToolRequest`, health, metadata, and limits.

## Root cause

Provider integration is a natural architectural pressure point: SDK convenience types can easily spread beyond the adapter unless boundaries are enforced mechanically.

## Investigation

Compared the 0.0.1 contracts to the current Responses API streaming/function-call event shapes and identified the minimum neutral additions needed: provider response ID/metadata, cancellation terminal state, and generic provider call ID on tool requests/results.

## Attempted fixes

No legacy V1 provider layer was copied. Direct SDK use outside the adapter was rejected as incompatible with the canonical V2 direction.

## Final fix

Implemented `providers/intelligence/openai/` as the only OpenAI SDK boundary, serialization helpers for context/tools/reasoning, and streaming translation into provider-neutral events. Added a repository test that rejects direct OpenAI SDK imports outside the adapter package.

## Regression tests

- `test_core_does_not_import_openai_sdk`
- `test_only_openai_provider_package_may_import_openai_sdk`
- `test_streams_text_and_completion_without_sdk_objects_leaking`
- `test_tool_call_becomes_non_executable_tool_request`
- `test_invalid_provider_tool_json_fails_closed`

## Verification / live outcome

Automated adapter tests pass using a fake async Responses stream. Real GPT-5.6 Luna verification remains pending the user's live acceptance because the delivery environment does not possess his API credentials.

## Regression risk

Future SDK upgrades, Responses API event changes, or new model capabilities could tempt business logic to special-case provider schemas outside this package.

## Technical lesson

Provider independence must be enforced by tests, not just comments. Translate SDK objects immediately at the adapter boundary and keep authority/execution contracts entirely separate.
