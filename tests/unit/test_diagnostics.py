import ast
import unittest
from pathlib import Path

from core.diagnostics import collect_diagnostics, read_version


ROOT = Path(__file__).resolve().parents[2]


class DiagnosticsTests(unittest.TestCase):
    def test_reports_provider_layer_without_live_network_probe(self) -> None:
        data = collect_diagnostics()
        self.assertEqual(data["version"], "0.0.2")
        self.assertEqual(data["status"], "ok")
        self.assertEqual(
            data["providers"],
            {
                "intelligence": "provider-layer-ready",
                "stt": "not-configured",
                "tts": "not-configured",
            },
        )
        self.assertEqual(data["network_probe"], "not-run")
        self.assertEqual(data["external_actions"], "disabled-in-core-diagnostics")
        self.assertEqual(read_version(), "0.0.2")

    def test_diagnostics_imports_no_network_or_process_modules(self) -> None:
        source = (ROOT / "core" / "diagnostics.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        forbidden = {"socket", "urllib", "http", "requests", "subprocess", "webbrowser", "openai"}
        self.assertTrue(imported.isdisjoint(forbidden), imported & forbidden)


if __name__ == "__main__":
    unittest.main()
