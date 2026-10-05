import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class Repair2RuntimeGitignoreTests(unittest.TestCase):
    def _active_gitignore_patterns(self) -> list[str]:
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        return [
            line.strip()
            for line in lines
            if line.strip() and not line.lstrip().startswith("#")
        ]

    def test_root_runtime_ignore_is_anchored(self) -> None:
        patterns = self._active_gitignore_patterns()
        self.assertIn(".runtime/", patterns)
        self.assertIn("/runtime/", patterns)
        self.assertNotIn(
            "runtime/",
            patterns,
            "A bare runtime/ rule also ignores core/runtime source code.",
        )

    def test_git_does_not_ignore_core_runtime_source(self) -> None:
        if shutil.which("git") is None or not (ROOT / ".git").exists():
            self.skipTest("Git repository metadata is not available in this test environment")

        source_probe = ROOT / "core" / "runtime" / "__init__.py"
        self.assertTrue(source_probe.exists(), "core/runtime source must exist before Repair2")

        source_result = subprocess.run(
            [
                "git",
                "check-ignore",
                "--quiet",
                "--no-index",
                "core/runtime/__init__.py",
            ],
            cwd=ROOT,
            check=False,
        )
        self.assertNotEqual(
            source_result.returncode,
            0,
            "core/runtime source is still being ignored by Git",
        )

        generated_result = subprocess.run(
            [
                "git",
                "check-ignore",
                "--quiet",
                "--no-index",
                "runtime/_jarvis_gitignore_probe",
            ],
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(
            generated_result.returncode,
            0,
            "root runtime/ generated data should remain ignored",
        )


if __name__ == "__main__":
    unittest.main()
