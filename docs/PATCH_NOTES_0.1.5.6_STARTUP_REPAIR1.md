# 0.1.5.6 Browser Bridge — Startup Repair 1

## Cause
The new `mini-overlap-luna-trim-guided-browser-bridge` launcher mode enables
`JARVIS_CORE_LUNA_PROBE` but was omitted from the enumerated `overlap_probe` and
`pcm_trim` groups. Consequently `apps/desktop_alpha.py` raises
`RuntimeError: Core Luna mode requires overlap and Core delegation orchestration`
when the assistant wakes. Browser Bridge itself was not yet exercised.

## Fix
Only the A/B launcher behavior is modified. Every mode already verified against
`MODELS` that begins with `mini-overlap` now enables overlap. Every validated
mode beginning with `mini-overlap-luna-trim` enables leading-silence PCM trim.
New launcher regression tests exercise the mode end-to-end without starting npm,
audio, the browser, or network requests. The script's usage text is updated.

No changes to voice models, browser adapter, extensions, existing policy,
request authorization, or Core delegation implementation.

## Apply (from project root; Jarvis fully closed)

1. Extract the ZIP to the root, without deleting prior installer files.
2. `python .\apply_0_1_5_6_browser_bridge_startup_repair1.py`
3. `python -m unittest tests.unit.test_0_1_5_6_browser_bridge_startup_repair1 -v`
4. `python -m unittest discover -s tests -q`
5. `npm run desktop:build`
6. Set `JARVIS_BROWSER_BRIDGE_EXTENSION_ID` in the same PowerShell session.
7. `python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-browser-bridge`

Expected launch heading: `core_luna=on`, `pcm_trim=on`, `delegation_guidance=on`,
`extension_browser=on`, `managed_browser=off`. After saying “Hey Jarvis”, there
must be **no** ASGI Core Luna/overlap runtime error. Then perform original 0.1.5.6
five voice tests and browser acceptance tests from
`docs/TESTING_GUIDE_0.1.5.6_BROWSER_BRIDGE.md`.

Do not commit or cleanup until live user acceptance. Installer takes a dedicated
backup and will refuse to modify a file whose code differs (other than CRLF/LF).
