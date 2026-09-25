# ISSUE_011 - Chatterbox Local Loader API Compatibility

## Status
Addressed by 0.0.4-repair6; pending live acceptance.

## Problem
Live provider-health testing reached the fully local Chatterbox Turbo loader and failed with `TypeError: ChatterboxTurboTTS.from_local() got an unexpected keyword argument 'nano'`. Jarvis had coded against a newer upstream signature while the isolated runtime intentionally pins `chatterbox-tts==0.1.7`.

## Resolution
The Turbo adapter now uses the common `from_local(model_dir, device=...)` call. Turbo selection is already guaranteed by the provider package and the required `t3_turbo_v1.safetensors` asset, so an explicit `nano=False` flag is unnecessary.

## Long-term rule
Provider adapters must code against the exact pinned runtime contract and avoid optional API parameters that are not needed to identify the selected provider/model. When supporting multiple provider package versions, prefer the smallest common API surface or an explicit compatibility shim covered by tests.
