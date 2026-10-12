# 0.1.3 Repair10 — Compound dismissal classified as ordinary gratitude

## Evidence
Repair9 live: `Thanks Jarvis, that's all` yielded `tool=none` and a direct farewell, whereas an earlier genuine sleep with `sleep_jarvis` succeeded through `verified_user_sleep_request`. The failure occurred in model route selection, not in transcript evidence validation.

## Narrow fix
Strengthen the silent decision instructions and the overlap tool description: prioritize a clear closing at the end of the same utterance over earlier politeness, contrast with gratitude alone, a continued question, a quotation, and a negated command. This is **model-based intent selection** and does not add any hard-coded lifecycle triggers. Keep same-turn transcript validation as the only sleep authorizer. No changes to voice/PCM, user response length, Luna provider, or Decisions.

## Validation / limits
Unit and source-policy tests cannot prove model compliance; live test compound sleep with natural speech multiple times. Watch for `sleep_evidence_check`, `phase=sleep`, and verified user sleep. Also test gratitude-alone and microphone noise. If misclassification persists, capture transcripts and tool decisions before considering a separate model-based intent adjudicator.
