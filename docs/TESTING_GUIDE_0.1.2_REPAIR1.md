# 0.1.2-repair1 — Delegation Truthfulness & Caption Continuity Testing Guide

Do not commit or delete patch artifacts until automated tests pass **and** live behavior is accepted.

## 1. Focused automated tests

```powershell
python -m unittest `
  tests.unit.test_0_1_2_repair1_delegation_caption_truthfulness `
  tests.unit.test_0_1_2_intelligence_router `
  tests.integration.test_0_1_2_realtime_delegation_router `
  tests.integration.test_0_1_2_conversation_provider_override `
  tests.integration.test_0_0_9_repair4_realtime_core_delegation -v
```

## 2. Full regression

```powershell
python -m unittest discover -s tests -v
```

## 3. Diagnostics

```powershell
python -m core.diagnostics
npm run desktop:check
```

If dependencies are already installed, also build the renderer:

```powershell
npm run desktop:build
```

## 4. Live reasoning-delegation test

Run:

```powershell
npm run desktop
```

Wake Jarvis and say:

**“Jarvis, use your Core to explain why idempotency matters when a client reconnects to a runtime.”**

Expected:

- Jarvis delegates immediately without a spoken “let me think / let me explain / give me a second” preamble.
- The first spoken content is the actual authoritative result.
- The visible caption continues through the full spoken response and does not stop mid-sentence.
- If a provider unexpectedly emits any pre-tool speech anyway, its visible caption must finish instead of cutting off while audio continues.

## 5. Fail-closed background-task test

Say:

**“Jarvis, use your Core to start a background task that builds a project while I’m gone.”**

Expected:

- Jarvis must **not** say that it is getting the task ready, starting it, queueing it, or otherwise imply execution before Core answers.
- Core returns the current `long_task` capability as unavailable.
- Jarvis states that limitation truthfully and briefly.
- No second sentence may contradict the unavailable result.
- The displayed text must match the spoken response through completion.

## 6. Wake/sleep regression

Verify one normal wake, one direct conversational answer, and one explicit sleep request still behave exactly as accepted in 0.1.1 Repair7.

## 7. Cleanup / commit — only after live acceptance

1. Remove the copied `Jarvis_Core_v2_0.1.2_repair1_patch.zip`, `apply_0_1_2_repair1_patch.py`, `patch_files/`, and `.patch_backups/` from the project root.
2. Do **not** delete `.env`, `.venv`, `.runtime`, user data, voice references, OAuth/account data, databases, logs, or the read-only V1 reference checkpoint.
3. Rerun the full regression and diagnostics.
4. Run `git diff --check` and `git status --short --untracked-files=all`.
5. Confirm no patch/apply/backup artifacts or private runtime data are staged.
6. Create one focused commit for accepted 0.1.2 including Repair1. Do not start 0.1.3 before that commit is clean.
