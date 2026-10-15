# ISSUE 106 — Browser action stuck Working and casual command refused

## Symptoms (Windows live run after Repair1)
- `Jarvis, can you open YouTube for me?` and `Could you please open YouTube?` worked and returned silently.
- `Hey go ahead and open YouTube` reached `test_action` but Core returned `user_request_does_not_authorize_action` because the independent safe grammar did not cover the affirmative lead-in.
- `Open Google` was correctly rejected by Core with the same nonauthorization code, but the desktop visually stayed on Working.

## Fix
- Narrow grammar extension for affirmative go-ahead lead-ins only, preserving allowlist and fail-closed behavior.
- Track action requests by dispatched turn and epoch independently of routing state. Timeout an unacknowledged Core result without repeating side effects, and return UI to Ready.
- Emit lightweight completion telemetry to compare Core and UI outcomes.

## Safety and acceptance
A Core browser launch is still contingent on a matching, confirmed, same-turn user transcript. No generic URL opening, shell command support, or automatic retries. Windows live tests pending.
