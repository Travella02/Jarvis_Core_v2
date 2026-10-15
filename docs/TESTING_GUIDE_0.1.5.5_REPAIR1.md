# Jarvis 0.1.5.5 Candidate1 Repair1 — Live Testing

Use the existing Candidate1 installation, without cleaning or committing. Close Jarvis.

## Commands, one at a time

```powershell
python .\apply_0_1_5_5_repair1_default_browser.py
```

```powershell
python -m unittest tests.unit.test_0_1_5_5_repair1_default_browser -v
```

```powershell
python -m unittest discover -s tests -q
```

```powershell
npm run desktop:build
```

```powershell
python .\scripts\realtime_ab.py mini-overlap-luna-trim-guided-browser-media
```

## Acceptance

1. Confirm Windows default browser in Settings > Apps > Default apps.
2. Wake with `Hey Jervis` and `Hey Dervis, what's seventeen times six?` and verify both wake and answer. Also verify no wake to ordinary speech such as `The service was nervous.`
3. Five regression utterances: `Hey Jarvis, what planet is called the Red Planet?`, `Go to sleep, Jarvis.`, `Jarvis, what's seventeen times six?`, `Thanks, Jarvis.`, `Thanks Jarvis, that's all.`
4. Ask `Open YouTube`, `Please open Google`, `Now open Wikipedia`, `Go to GitHub`, `Search YouTube for videos about black holes` (single action per utterance). All should open in the **Windows default browser**, no separate Jarvis-controlled browser. Verify Google/YouTube still open after tab opening/closing in the normal browser.
5. `Do not open YouTube`, `Open Google and send an email`, `Open YouTube tomorrow` must not open.
6. `Please open YouTube in your managed browser` should open a separate Jarvis-managed Playwright window. Then `Close this tab` applies **only** to that managed window. Test `Pause the video` there only after manually starting an HTML5 video. For a video in the OS-default browser, Jarvis should **not** claim control.
7. `Can you close my default browser's YouTube tab?` should **not** silently close a managed tab or claim it was done; the cross-browser control bridge is not yet implemented.
8. Check voice latency on short arithmetic and science questions: compare with accepted 0.1.5.4 checkpoint (~0.6–1.2 s first audio in ordinary turns). Report if significantly slower.

No git commit or patch/backups cleanup before live acceptance. If any command fails, share screenshot and terminal output; do not repeat apply.
