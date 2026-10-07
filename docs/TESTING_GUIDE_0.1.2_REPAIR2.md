# 0.1.2-repair2 — Silent Delegation Boundary Testing Guide

Do not commit or delete patch artifacts until automated tests pass **and** live behavior is accepted.

## 1. Focused automated tests

```powershell
python -m unittest `
  tests.unit.test_0_1_2_repair1_delegation_caption_truthfulness `
  tests.unit.test_0_1_2_repair2_delegation_preamble_suppression `
  tests.unit.test_0_1_2_intelligence_router `
  tests.integration.test_0_1_2_realtime_delegation_router `
  tests.integration.test_0_1_2_conversation_provider_override `
  tests.integration.test_0_0_9_repair4_realtime_core_delegation -v
```

Expected: **27 tests pass**.

## 2. Full regression

```powershell
python -m unittest discover -s tests -v
```

Expected: **505 tests pass with the existing 1 skip**.

## 3. Diagnostics

```powershell
python -m core.diagnostics
```

Expected: final line `Status: ok`.

```powershell
npm run desktop:check
```

If dependencies are installed, also run:

```powershell
npm run desktop:build
```

## 4. Live test 1 — reasoning delegation stays invisible

Start Jarvis and wake him normally. Say exactly:

**“Jarvis, use your Core to explain why idempotency matters when a client reconnects to a runtime.”**

Expected:

- no audible or visible “let me pull in Core”, “let me think”, “I’m delegating that”, “I’m routing that”, or similar internal narration;
- the UI may show **WORKING** while the delegated reasoning is pending;
- the first user-facing speech is the actual useful explanation;
- the actual explanation types out normally with the spoken response and remains complete;
- no internal preamble suddenly appears, disappears, or replaces the final answer.

## 5. Live test 2 — unsupported background work cannot fake progress

Say exactly:

**“Jarvis, use your Core to start a background task that builds a project while I’m gone.”**

Expected:

- no audible or visible “okay, let me get that started”, “I’ll queue that”, “I’m preparing it”, or similar progress claim;
- the UI may show **WORKING** briefly;
- the first user-facing response is the truthful unavailable result;
- Jarvis clearly says that durable/background build work is not available in this build yet;
- the final spoken and visible response agree and remain complete.

## 6. Quick direct-answer regression

Ask one ordinary question that should **not** require delegation, for example:

**“Jarvis, what is 12 times 8?”**

Expected:

- immediate normal Realtime answer;
- no WORKING state caused by the delegation suppression path;
- audio and caption streaming remain normal.

## 7. Wake/sleep regression

Verify one normal wake and one explicit sleep request still behave exactly as accepted in 0.1.1 Repair7.

## 8. Cleanup / commit — only after live acceptance

1. Remove the copied `Jarvis_Core_v2_0.1.2_repair2_patch.zip`, `apply_0_1_2_repair2_patch.py`, `patch_files/`, and `.patch_backups/` from the project root.
2. Also remove leftover Repair1 patch ZIP/apply payload artifacts if they are still present.
3. Do **not** delete `.env`, `.venv`, `.runtime`, user data, voice references, OAuth/account data, databases, logs, or the read-only V1 reference checkpoint.
4. Rerun the full regression and diagnostics.
5. Run `git diff --check` and `git status --short --untracked-files=all`.
6. Confirm no patch/apply/backup artifacts or private runtime data are staged.
7. Create one focused commit for accepted 0.1.2 including Repairs 1 and 2. Do not start 0.1.3 before that commit is clean.
