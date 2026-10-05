# Jarvis Core v2 0.0.7 Repair2 — Testing Guide

## 1. Apply Repair2

Extract the Repair2 ZIP into the existing Jarvis Core v2 project root and run:

```powershell
python apply_0_0_7_repair2_patch.py
```

The installer must refuse to proceed if `VERSION` is not `0.0.7` or the local
`core/runtime/__init__.py` source file is missing.

## 2. Verify Git ignore behavior

The real source package must no longer be ignored:

```powershell
git check-ignore -v --no-index core/runtime/__init__.py
$LASTEXITCODE
```

Expected: no ignore-rule output and exit code `1`.

The root generated runtime directory must still be ignored:

```powershell
git check-ignore -v --no-index runtime/_jarvis_gitignore_probe
$LASTEXITCODE
```

Expected: `.gitignore` reports `/runtime/` and exit code `0`.

Then:

```powershell
git status --short core/runtime
```

Expected on the current working tree: the previously hidden `core/runtime`
source files become visible to Git (typically as untracked files until the final
0.0.7 commit). Do not commit yet.

## 3. Focused Repair1 + Repair2 checks

```powershell
python -m unittest `
  tests.unit.test_0_0_7_repair1_dependency_compatibility `
  tests.unit.test_0_0_7_repair2_gitignore_runtime `
  tests.unit.test_foundation_structure -v
```

Expected: all tests pass. The Repair2 Git behavior test runs fully in the real
repository; it may skip only when Git repository metadata is intentionally not
present, such as an exported source archive.

## 4. Continue normal 0.0.7 acceptance

After the focused checks pass, continue the existing 0.0.7 sequence:

```powershell
python -m unittest discover -s tests -v
```

Then:

```powershell
python -m apps.runtime_api_lab
```

Do not clean patch artifacts or commit until 0.0.7 passes live acceptance.
