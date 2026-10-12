# Repair6-Repair7 validation

1. `python -m unittest tests.unit.test_0_1_2_repair6_repair7_probe_vad_lifecycle tests.unit.test_0_1_2_repair6_repair6_tool_selection_probe -v`
2. `python -m unittest discover -s tests -v`
3. `python -m core.diagnostics`
4. `npm run desktop:check` and `python .\scripts\realtime_ab.py mini-tools` (on Windows, after install)
5. Say: **Jarvis, what planet is known as the Red Planet?** Expect a numbered `[USER SPEECH]`, a `[Jarvis Tool Probe]` direct decision and a text-only `[JARVIS REPLY]`. No audio.
6. Say: **Jarvis, analyze the tradeoffs of event sourcing in a complex distributed application.** Expect a tool-selection decision (if chosen) that is dry-run and does not execute Luna.
7. Say: **Jarvis, start a background build while I'm gone.** Expect simulated unavailable action with `executed=false`; no work starts.
8. If this still fails, send terminal events including errors. Don't commit until live accepted.
