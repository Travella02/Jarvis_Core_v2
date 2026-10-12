# ISSUE 080 — Windows unit test UTF-8 source reading (0.1.3 Repair3)

## Symptom
`python -m unittest tests.unit.test_0_1_3_repair2_core_luna -v` reported
`UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d` while a unit test
read `apps/desktop/ui/src/App.tsx` using the Windows Python 3.11 default cp1252 codec.
The other twelve focused tests passed; the exception was in test-source inspection,
not in the Core Luna execution path.

## Minimal repair
Specify `encoding='utf-8'` for all five `Path.read_text` calls in the
Repair2 test's `SourceContracts`. No production modules, audio, model prompts,
permissions, routing, or API behavior are changed.

## Acceptance
Run the focused unit tests, full Python suite, Core diagnostics and desktop
check on Windows. Continue the planned live Luna delegation tests afterward.
Do not clean temporary patch artifacts or commit before live acceptance.
