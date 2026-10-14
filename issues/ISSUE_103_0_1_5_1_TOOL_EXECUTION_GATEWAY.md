# ISSUE 103 — Core action execution not implemented in accepted 0.1.4

**Status:** candidate foundation; end-to-end live bridge remains pending

Prior: All external-action selections in Realtime Mini experimental tool probe were intentionally `test_action` dry runs. The model could select an action, but Core provided no authorized executor.

Focused solution in 0.1.5.1: a stand-alone Core-owned gateway with exact allowlist, independent confirmed-turn evidence, replay protection and correct result semantics. Only explicit `scripts/tool_gateway_demo.py --open-youtube` makes a visible OS request. No changes to voice or any provider.

Next: wire voice/typed selections through Core after verified same-turn transcript with approval policy and never release a positive voice response before Core's result. Add browser-failure and stale-turn tests. Avoid introducing new barge-in handling or unsolicited microphone changes.
