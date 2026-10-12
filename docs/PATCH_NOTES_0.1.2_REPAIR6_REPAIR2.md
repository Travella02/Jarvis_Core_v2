# 0.1.2 Repair6-Repair2 — Natural conversational sleep routing

**Trigger:** The user said `Thanks Jarvis, that's all.` with accurate ASR, but the cloud router selected `route=direct`, and Jarvis spoke a social reply instead of entering local sleep. This was a model routing decision error, not a microphone, audio transport, or bridge malfunction.

**Fix:** Strengthen the existing *semantic* silent router's sleep definition, and its function parameter description. A clear conversational sign-off paired with a thank-you/Jarvis's name should route `sleep`; thank-you alone or a continued question should not. The authoritative `route=sleep` bridge, local wake, pre-speech gate, direct voice, Core delegation, and Repair6 shadow machinery are untouched.

**Limits:** Prompt correction improves model odds but isn't a deterministic guarantee: the router is model-based. Only an actual live voice test can establish whether the phrasing now routes correctly. No phrase-specific code shortcut was introduced.

**Repair6 data:** `route_ms=397` on the first direct turn, while speculative text produced first token at 462 ms and was then canceled (578 ms). Luna was canceled before first token. The first direct `speech_end->first_audio=1794 ms`, compared with prior ~800-1000 ms direct results without shadow. A single sample cannot attribute the regression to the shadow path. A controlled A/B test is required before starting audio speculation.

**Validation:** Five focused new tests, 541 full tests (1 existing skip), local diagnostics `Status: ok`, and desktop static check passed. The new tests cover prompt semantics plus silent lifecycle and direct-branch behavior; they don't emulate the Realtime model's classification.

**Acceptance:** Live-test a polite end-of-session phrase and non-sleep gratitude, verify only one correct action and no leaked audio, then measure shadow on/off performance before developing speculative audio.

Do not commit or remove patch artifacts until live acceptance.
