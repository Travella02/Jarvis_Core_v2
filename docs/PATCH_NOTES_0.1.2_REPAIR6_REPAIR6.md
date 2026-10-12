# Repair6-Repair6 — Gate-free tool-selection probe

- Opt-in text-only tool selection: `mini-tools` / `full-tools`.
- Exactly one Realtime response with `tool_choice=auto`, no mandatory route gate. Tools: `ask_luna` and `test_action` **dry-run only**.
- No user-facing audio and no real tool invocation. All results explicitly carry `executed=false`.
- The provider's action/tool calls never reach Core's execution bridge; all tool results are synthetic.
- Terminal labels `[Jarvis Tool Probe]`, `[USER SPEECH]`, `[JARVIS REPLY]`, token/cost summary.
- Compares tool-selection appropriateness without opening the pre-tool audio leak V1/Repair1 discovered.
- This is not yet tool-enabled spoken Jarvis or an actual Luna execution benchmark.
- Existing routed and no-tools fast modes remain unmodified by default.
- No file, email, calendar, browser, or device actions run.
- Don't accept/commit before live Windows testing.
