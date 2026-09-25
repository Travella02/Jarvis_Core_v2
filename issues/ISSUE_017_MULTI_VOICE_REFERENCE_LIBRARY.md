# ISSUE_017 — Multi-Voice Reference Library

## Problem

Voice Lab accepted raw `--voice-ref` paths, which made repeated Qwen cloning tests cumbersome and provided no durable provider-neutral place for multiple user/ORVEX voice identities.

## Repair12 decision

Store personal/reference audio only under ignored runtime user data at `.runtime/voice/references/<profile-id>/`. Each profile has a JSON manifest, one or more copied reference clips, and a primary reference ID. Core resolves that data to the existing `VoiceProfile` contract.

TTS providers remain replaceable. No Qwen- or Chatterbox-specific persistence is allowed in Conversation Core.

## Follow-up

Voice Studio later needs consent/rights metadata, enrollment UI, deletion/export flows, quality scoring, and secure per-account storage/sync rules. Those are not part of Voice Lab repair12.
