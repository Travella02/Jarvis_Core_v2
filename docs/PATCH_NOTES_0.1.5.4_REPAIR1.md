# 0.1.5.4 Repair1 — Managed browser launch Core/Luna flag

## Reproduction
`mini-overlap-luna-trim-guided-managed-browser` enabled delegation guidance and overlap but not `JARVIS_CORE_LUNA_PROBE`.
The desktop backend refused the WebSocket on wake: `RuntimeError: 0.1.4.1 guidance requires real Core/Luna overlap mode`.

## Focused fix
Include the new managed-browser mode in the existing `luna_probe` mode set in `scripts/realtime_ab.py`.
Nothing else in the voice path, UI, browser implementation, permission rules, or model configuration changes.
The new regression test captures actual launch subprocess environment and asserts all expected flags are enabled;
it separately verifies the accepted semantic mode and isolation of earlier modes.

## Safe install
Stop Jarvis. Extract the entire repair ZIP into the Jarvis repository root. Run `python .\apply_0_1_5_4_repair1.py`.
Installer verifies the currently installed 0.1.5.4 script hash and rejects an already applied patch.
Do not clean up patch artifacts, backups, or commit until live acceptance.

## Verify
- `python -m unittest tests.unit.test_0_1_5_4_repair1_startup -v`
- `python -m unittest discover -s tests -q`
- `npm run desktop:build`
- `python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-managed-browser`

Expected launch header includes `core_luna=on`, `delegation_guidance=on`, `managed_browser=on`.
Wake Jarvis, ask a simple question, then ask to open Google, Wikipedia and switch tabs. Request a negated action ('Don't open YouTube'); it must not execute.
Windows live browser operation, startup latency, and microphone behavior are not verified by these unit tests.
