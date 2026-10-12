"""Gate-free *conversation-only* A/B contract tests; no API calls."""
from pathlib import Path
import unittest

from providers.voice_frontend.openai_realtime.config import OpenAIRealtimeConfig
from providers.voice_frontend.openai_realtime.webrtc import DIRECT_ONLY_BENCHMARK_INSTRUCTIONS

ROOT = Path(__file__).resolve().parents[2]

class GateFreeABTests(unittest.TestCase):
    def test_default_keeps_safe_routing(self):
        c = OpenAIRealtimeConfig.from_env(env={"OPENAI_API_KEY": "fake"})
        self.assertFalse(c.direct_only_benchmark)

    def test_mode_opt_in(self):
        c = OpenAIRealtimeConfig.from_env(env={"JARVIS_REALTIME_DIRECT_ONLY_BENCHMARK": "1"})
        self.assertTrue(c.direct_only_benchmark)

    def test_invalid_mode_rejected(self):
        with self.assertRaises(ValueError):
            OpenAIRealtimeConfig.from_env(env={"JARVIS_REALTIME_DIRECT_ONLY_BENCHMARK": "maybe"})

    def test_fast_policy_disables_all_tools(self):
        src = (ROOT / 'apps/desktop_alpha.py').read_text(encoding='utf-8')
        for exact in ('"tools": []', '"tool_choice": "none"', '"output_modalities": ["audio"]',
                      '"direct_only_benchmark": direct_only', 'DIRECT_ONLY_BENCHMARK_INSTRUCTIONS'):
            self.assertIn(exact, src)

    def test_safe_policy_remains(self):
        src = (ROOT / 'apps/desktop_alpha.py').read_text(encoding='utf-8')
        self.assertIn('"output_modalities": ["text"]',src)
        self.assertIn('"tool_choice": {"type": "function", "name": ROUTE_TURN_TOOL_NAME}',src)
        self.assertIn('TURN_ROUTER_INSTRUCTIONS',src)

    def test_forbidden_tool_event_rejected(self):
        src = (ROOT / 'apps/desktop_alpha.py').read_text(encoding='utf-8')
        self.assertIn('if self.config.direct_only_benchmark and str(event.get("type") or "") == "response.function_call_arguments.done":',src)

    def test_renderer_no_route_and_no_shadow(self):
        src = (ROOT / 'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
        self.assertIn("kind: 'desktop_fast_direct'",src)
        self.assertIn("latencyRef.current.route = 'direct_no_gate'",src)
        self.assertIn('if (!directOnlyBenchmarkRef.current) requestParallelShadow()',src)
        self.assertIn('if (!directOnlyBenchmarkRef.current) requestParallelShadow(dc)',src)
        self.assertIn('payload.direct_only_benchmark === true',src)

    def test_instruction_discourages_fake_claims(self):
        self.assertIn('Never pretend',DIRECT_ONLY_BENCHMARK_INSTRUCTIONS)
        self.assertIn('no tools',DIRECT_ONLY_BENCHMARK_INSTRUCTIONS)

    def test_launcher_has_both_modes_both_models(self):
        src = (ROOT / 'scripts/realtime_ab.py').read_text(encoding='utf-8')
        for marker in ('"mini-fast"', '"full-fast"', '"mini"', '"full"',
                       'JARVIS_REALTIME_DIRECT_ONLY_BENCHMARK'):
            self.assertIn(marker,src)

if __name__=='__main__': unittest.main()
