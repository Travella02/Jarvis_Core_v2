# Testing — 0.0.5 Repair5c

Focused:
`python -m unittest tests.unit.test_0_0_5_repair5c_windows_dll_loader tests.unit.test_0_0_5_repair5_silero_presence -v`

Full:
`python -m unittest discover -s tests -v`

Then retry the existing Voice Lab command. No reinstall of the Silero model is
needed.

If native loading still fails, Repair5c now prints the DLL search directories and
the sibling whisper/ggml DLLs so the missing dependency can be identified without
guessing.
