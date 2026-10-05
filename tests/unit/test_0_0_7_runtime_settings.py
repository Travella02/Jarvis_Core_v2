import unittest

from core.runtime import RuntimeSettings, RuntimeSettingsError


class RuntimeApiSettingsTests(unittest.TestCase):
    def test_runtime_api_defaults_to_loopback_and_non_v1_port(self) -> None:
        settings = RuntimeSettings()
        self.assertEqual(settings.api_host, "127.0.0.1")
        self.assertEqual(settings.api_port, 8766)
        self.assertEqual(settings.public_dict()["api_exposure"], "loopback-only")

    def test_runtime_api_accepts_ipv6_loopback(self) -> None:
        settings = RuntimeSettings(api_host="::1")
        self.assertEqual(settings.api_host, "::1")

    def test_runtime_api_rejects_unauthenticated_lan_exposure(self) -> None:
        for host in ("0.0.0.0", "192.168.1.10", "10.0.0.5"):
            with self.subTest(host=host):
                with self.assertRaises(RuntimeSettingsError):
                    RuntimeSettings(api_host=host)

    def test_environment_values_are_explicit_and_bounded(self) -> None:
        settings = RuntimeSettings.from_env(
            {
                "JARVIS_RUNTIME_API_HOST": "localhost",
                "JARVIS_RUNTIME_API_PORT": "9001",
                "JARVIS_RUNTIME_API_EVENT_QUEUE": "128",
                "JARVIS_RUNTIME_API_MAX_REPLAY": "256",
                "JARVIS_RUNTIME_API_HEARTBEAT_SECONDS": "9.5",
            }
        )
        self.assertEqual(settings.api_host, "localhost")
        self.assertEqual(settings.api_port, 9001)
        self.assertEqual(settings.api_event_queue_limit, 128)
        self.assertEqual(settings.api_max_replay_events, 256)
        self.assertEqual(settings.api_heartbeat_seconds, 9.5)


if __name__ == "__main__":
    unittest.main()
