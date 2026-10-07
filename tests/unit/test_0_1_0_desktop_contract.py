import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class DesktopAlphaContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.electron = (ROOT / "apps" / "desktop" / "electron" / "main.cjs").read_text(encoding="utf-8")
        self.app = (ROOT / "apps" / "desktop" / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")
        self.styles = (ROOT / "apps" / "desktop" / "ui" / "src" / "styles.css").read_text(encoding="utf-8")
        self.host = (ROOT / "apps" / "desktop_alpha.py").read_text(encoding="utf-8")

    def test_candidate_version_and_electron_entrypoint(self) -> None:
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "0.1.2")
        self.assertEqual(self.package["version"], "0.1.2")
        self.assertEqual(self.package["main"], "apps/desktop/electron/main.cjs")

    def test_desktop_scripts_build_before_electron_launch(self) -> None:
        self.assertIn("desktop:build", self.package["scripts"])
        self.assertEqual(self.package["scripts"]["desktop"], "npm run desktop:build && electron .")
        self.assertIn("node --check apps/desktop/electron/main.cjs", self.package["scripts"]["desktop:check"])

    def test_react_typescript_and_electron_dependencies_are_explicit(self) -> None:
        self.assertIn("react", self.package["dependencies"])
        self.assertIn("react-dom", self.package["dependencies"])
        self.assertIn("electron", self.package["devDependencies"])
        self.assertIn("vite", self.package["devDependencies"])
        self.assertIn("typescript", self.package["devDependencies"])

    def test_electron_renderer_is_hardened_and_loopback_scoped(self) -> None:
        self.assertIn("contextIsolation: true", self.electron)
        self.assertIn("nodeIntegration: false", self.electron)
        self.assertIn("sandbox: true", self.electron)
        self.assertIn("127.0.0.1", self.electron)
        self.assertIn("setPermissionRequestHandler", self.electron)
        self.assertIn("setWindowOpenHandler", self.electron)

    def test_electron_owns_single_core_process_and_preflights_port(self) -> None:
        self.assertIn("requestSingleInstanceLock", self.electron)
        self.assertIn("portInUse", self.electron)
        self.assertIn("apps.desktop_alpha", self.electron)
        self.assertIn("coreOwned", self.electron)
        self.assertIn("Port ${CORE_PORT} is already in use", self.electron)

    def test_electron_gracefully_ends_realtime_before_owned_core(self) -> None:
        self.assertIn("/api/realtime/end", self.electron)
        self.assertIn("before-quit", self.electron)
        self.assertIn("stopOwnedCore", self.electron)

    def test_renderer_is_intentionally_minimal(self) -> None:
        self.assertIn("<ParticleOrb", self.app)
        self.assertIn("Ask Jarvis…", self.app)
        self.assertIn("Speak naturally, or type instead.", self.app)
        self.assertNotIn("sidebar", self.app.lower())
        self.assertNotIn("settings", self.app.lower())

    def test_avatar_has_all_initial_product_states(self) -> None:
        for state in ("connecting", "idle", "listening", "thinking", "speaking", "working", "error"):
            self.assertIn(state, self.app)
        for selector in ("avatar--listening", "avatar--thinking", "avatar--speaking", "avatar--working"):
            self.assertIn(selector, self.styles)

    def test_live_caption_uses_realtime_audio_transcript_deltas(self) -> None:
        self.assertIn("response.output_audio_transcript.delta", self.app)
        self.assertIn("enqueueCaptionDelta(event.delta || '')", self.app)
        self.assertIn("captionSourceRef", self.app)
        self.assertNotIn("setCaption((current) => `${current}${event.delta || ''}`)", self.app)

    def test_typed_input_stays_in_same_realtime_conversation(self) -> None:
        self.assertIn("conversation.item.create", self.app)
        self.assertIn("type: 'input_text'", self.app)
        self.assertIn("type: 'response.create'", self.app)
        self.assertNotIn("/runtime/v1/runtime/commands/typed", self.app)

    def test_renderer_never_contains_project_api_key(self) -> None:
        combined = self.app + self.electron + self.styles
        self.assertNotIn("OPENAI_API_KEY", combined)
        self.assertNotIn("Authorization: Bearer", combined)

    def test_desktop_host_reuses_authoritative_runtime_and_realtime_bridge(self) -> None:
        self.assertIn("JarvisRuntime", self.host)
        self.assertIn("RealtimeCoreBridge", self.host)
        self.assertIn("create_runtime_api(runtime)", self.host)
        self.assertIn("app.mount(\"/runtime\"", self.host)
        self.assertIn("host is loopback-only", self.host)

    def test_generated_desktop_artifacts_are_gitignored(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("node_modules/", gitignore)
        self.assertIn("dist/", gitignore)


if __name__ == "__main__":
    unittest.main()
