# 0.0.3 Live Acceptance - Conversation Core

Run from the `Jarvis_Core_v2` project root with `.venv` active.

## 1. Automated regression

```powershell
python -m unittest discover -s tests -v
```

Expected: all tests pass with `OK`.

## 2. Local diagnostics (no network)

```powershell
python -m core.diagnostics
```

Expected: version `0.0.3`, Conversation `context=ready`, `referents=ready`, `events=ready`, `state=ready`, `typed=ready`, `Status: ok`.

## 3. Deterministic Conversation Core benchmark (no network)

```powershell
python -m apps.conversation_benchmark
```

Expected: six PASS lines and `Result: 6/6 passed`, including `v1_resume_it_prefers_discussed_task` and `material_ambiguity_requests_clarification`.

## 4. Referent demo (no network)

```powershell
python -m apps.conversation_lab --context-demo
```

Expected:

- `resume it` resolves to the focused **task** even while a YouTube media referent is active.
- `resume the YouTube video` resolves explicitly to **media**.

## 5. Live shared-context Luna test

Uses the same local `.env` accepted in 0.0.2.

```powershell
python -m apps.conversation_lab --turn "For this conversation, remember the test word bluejay." --turn "What test word did I ask you to remember? Reply with only the word." --reasoning quick
```

Expected:

- Both turns report `Status: completed`.
- The second Jarvis response contains `bluejay`.
- Both turns have different `turn=` and `cancel=` IDs.
- Final context reports `state: listening`, `transcript_entries: 4`, and no active cancellation IDs.

This is a live model behavior test, so punctuation/casing may vary; shared-context recall is the acceptance target.

## 6. Interactive start command

```powershell
python -m apps.conversation_lab
```

Send two ordinary messages. `/context` must show one conversation with growing transcript history. `/events` must show typed input, state, routing, response, and completion events. `/quit` exits.

No browser, microphone, tool action, permission prompt, account action, or OS action should occur in 0.0.3.

## 7. Git inspection

```powershell
git status --short
```

Do not clean patch artifacts or commit until live acceptance passes.
