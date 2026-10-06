import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from apps.desktop_alpha import create_desktop_app
from tests.integration.test_0_1_0_desktop_host import runtime_with_provider
from providers.voice_frontend.openai_realtime import OpenAIRealtimeConfig


class DesktopRepair1RoutingTests(unittest.TestCase):
    def test_static_ui_is_served_by_http_routes_without_consuming_websockets(self) -> None:
        runtime, provider = runtime_with_provider()
        config = OpenAIRealtimeConfig(api_key="test-key")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text("<html>Jarvis</html>", encoding="utf-8")
            assets = root / "assets"
            assets.mkdir()
            (assets / "app.js").write_text("console.log('jarvis')", encoding="utf-8")
            app = create_desktop_app(runtime=runtime, provider=provider, realtime_config=config, static_dir=root)
            with TestClient(app) as client:
                self.assertEqual(client.get("/").status_code, 200)
                asset = client.get("/assets/app.js")
                self.assertEqual(asset.status_code, 200)
                self.assertIn("jarvis", asset.text)
                self.assertEqual(client.get("/not-a-real-route").status_code, 200)
                with self.assertRaises(WebSocketDisconnect):
                    with client.websocket_connect("/assets/not-a-websocket"):
                        pass

    def test_control_websocket_still_has_priority_over_spa_fallback(self) -> None:
        runtime, provider = runtime_with_provider()
        config = OpenAIRealtimeConfig(api_key="test-key")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text("<html>Jarvis</html>", encoding="utf-8")
            app = create_desktop_app(runtime=runtime, provider=provider, realtime_config=config, static_dir=root)
            with TestClient(app) as client:
                with client.websocket_connect("/ws/control") as websocket:
                    # A connected control channel proves the SPA fallback did not receive this websocket scope.
                    websocket.close()


if __name__ == "__main__":
    unittest.main()
