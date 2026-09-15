# Testing Guide — 0.0.1 - Foundation

## Automated test

From the `Jarvis_Core_v2` project root with the project virtual environment active:

```powershell
python -m unittest discover -s tests -v
```

Expected: all tests pass.

## Focused diagnostic tests

Run:

```powershell
python -m core.diagnostics
python -m core.diagnostics --json
```

Expected text output must include:

- `Jarvis Core v2 0.0.1 - Foundation diagnostics`
- Contracts ready for intelligence, tools, and voice
- Intelligence/STT/TTS providers all `not-configured`
- External actions `disabled-in-0.0.1-diagnostics`
- `Status: ok`

The JSON command must report the same facts in machine-readable form.

## Live acceptance checklist

1. Confirm the diagnostic commands return immediately without opening a browser, microphone permission prompt, app window, File Explorer, or network/login flow.
2. Confirm no provider/API key is required.
3. Confirm `Reference_jarvis_corev1/Jarvis_0.3.6_clean_checkpoint.zip` still exists and was not modified/replaced.
4. Run `git status --short` and confirm the intentional v2 foundation files are present while `.venv/` and temporary patch artifacts remain untracked/ignored as expected.
5. Do **not** commit yet. Report the live results first so acceptance/repair can be recorded.

If any item fails, remain on `0.0.1` and create `0.0.1-repair1`; do not move to 0.0.2.
