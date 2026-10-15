# 0.1.5.2 Testfix1 — Windows test decoding compatibility

- **Issue:** `IntegrationContracts.test_ui_action_waits_for_independent_matching_item` errored with `UnicodeDecodeError` in Windows Python, because `Path.read_text()` uses the system default (`cp1252`).
- **Repair:** Three source-file reads in `tests/unit/test_0_1_5_2_natural_actions.py` now pass `encoding='utf-8'` explicitly.
- **Scope:** Unit-test compatibility only; no Jarvis runtime, routing, audio, action policy, or tool-gateway behavior changes.
- **Acceptance:** Run focused test, full Python suite, then resume the original 0.1.5.2 Windows live tests. Do not clean or commit until live acceptance.
