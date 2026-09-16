# 0.0.2 - Intelligence Provider testing guide

## 1. Apply patch

From the `Jarvis_Core_v2` project root with the virtual environment activated:

```powershell
python apply_0.0.2_patch.py
```

The installer must report `Applied Jarvis Core v2 0.0.2 - Intelligence Provider` and create a timestamped `.patch_backups/0.0.2_*` folder.

## 2. Install/update the pinned provider dependency

```powershell
python -m pip install -r requirements.txt
```

Do not paste an API key into chat.

## 3. Configure the local development key

If `.env` does not already exist:

```powershell
Copy-Item .env.example .env
```

Open `.env` locally and replace `OPENAI_API_KEY=replace_me_in_local_env_only` with your development API key. `.env` is Git-ignored and must never be committed.

## 4. Automated tests

```powershell
python -m unittest discover -s tests -v
```

Expected: 33 tests pass. Automated tests do not require the API key and do not make live OpenAI requests.

## 5. Local-only diagnostics

```powershell
python -m core.diagnostics
python -m apps.intelligence_lab --status
```

Expected core diagnostics: version `0.0.2`, status `ok`, network probe `not-run`.

Expected provider status after dependency/key setup: provider `openai`, model `gpt-5.6-luna`, health `configured`, tools/vision/reasoning `yes`, and `Network probe: not run`.

## 6. Live Luna streaming acceptance

```powershell
python -m apps.intelligence_lab --prompt "Reply with exactly: Luna online." --reasoning quick
```

Expected: output streams from `openai/gpt-5.6-luna`, contains `Luna online.`, and ends with `Status: completed`.

No browser, microphone, operating-system action, or Jarvis tool execution should occur.

## 7. Live tool-authority acceptance

```powershell
python -m apps.intelligence_lab --tool-probe --reasoning quick
```

Expected:

```text
ToolRequest received: jarvis_test_probe(value='provider-boundary-ok')
Execution: BLOCKED BY DESIGN - provider emitted intent only; no tool executor was called
Status: completed
```

The probe must not execute any external action.

## 8. Live benchmark seed

```powershell
python -m apps.intelligence_benchmark
```

Expected: `3/3 passed`, including the V1 regression phrase `Can you open a new tab, please?` mapping to the benchmark-only browser tool request.

## 9. Git review

```powershell
git status --short
```

Do not clean patch artifacts or commit until live acceptance is confirmed. Any failure remains on 0.0.2 and receives a `0.0.2-repairN` patch.

## Development start command for this milestone

There is no desktop/conversation runtime yet. The 0.0.2 interactive development entry point is:

```powershell
python -m apps.intelligence_lab
```
