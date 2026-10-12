# Repair6-Repair6 live testing (text only)

1. Run `python scripts/realtime_ab.py mini-tools` (do not change .env).
2. Speak `Jarvis, what planet is known as the Red Planet?` Expected: direct text reply; NO `[Jarvis Tool Probe]` selection.
3. Speak `Jarvis, what is seventeen times six?` Expected: `102`, direct text.
4. Speak `Jarvis, analyze event sourcing tradeoffs in a complex distributed application.` Expected: model may select `ask_luna`, recorded as dry-run; NO actual Luna call.
5. Speak `Jarvis, start a background build while I am gone.` Expected: `test_action`, status unavailable, never claims work began.
6. Say a conversational follow-up. Confirm only one final text response per turn.
7. Close Jarvis and repeat with `python scripts/realtime_ab.py full-tools`.
8. Include `[Jarvis Tool Probe]`, `[JARVIS REPLY]`, `[Desktop response budget]` lines. Voice/speech latency is intentionally not measured in this TEXT-ONLY experiment.
Do not accept or commit until live tests pass. Do not delete patches/backups until then.
