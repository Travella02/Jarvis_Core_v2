"""Safe single-pass text-only tool-selection experiment; no external API calls."""
from pathlib import Path
import unittest
from providers.voice_frontend.openai_realtime.config import OpenAIRealtimeConfig
from providers.voice_frontend.openai_realtime.tool_probe import (
    ALLOWED_PROBE_TOOLS, TOOL_PROBE_TOOLS, TOOL_PROBE_INSTRUCTIONS,
    probe_response_policy, dry_run_result,
)

ROOT = Path(__file__).resolve().parents[2]

class ToolSelectionProbeTests(unittest.TestCase):
    def test_default_disabled(self):
        self.assertFalse(OpenAIRealtimeConfig.from_env(env={}).tool_selection_probe)

    def test_opt_in(self):
        self.assertTrue(OpenAIRealtimeConfig.from_env(env={'JARVIS_REALTIME_TOOL_SELECTION_PROBE':'1'}).tool_selection_probe)

    def test_invalid_bool_rejected(self):
        with self.assertRaises(ValueError):
            OpenAIRealtimeConfig.from_env(env={'JARVIS_REALTIME_TOOL_SELECTION_PROBE':'invalid'})

    def test_only_two_dry_run_tools(self):
        self.assertEqual({x['name'] for x in TOOL_PROBE_TOOLS}, ALLOWED_PROBE_TOOLS)
        self.assertEqual(ALLOWED_PROBE_TOOLS, {'ask_luna','test_action'})

    def test_single_pass_text_auto(self):
        p=probe_response_policy()
        self.assertEqual(p['output_modalities'], ['text'])
        self.assertEqual(p['tool_choice'], 'auto')
        self.assertNotIn('audio',p['output_modalities'])
        self.assertEqual(p['metadata']['jarvis_stage'],'tool_probe')
        self.assertEqual(p['tools'], TOOL_PROBE_TOOLS)

    def test_dry_run_luna_and_action_have_no_execution(self):
        for name, args in [('ask_luna',{'question':'code'}),('test_action',{'request':'build','execution':'background'})]:
            result=dry_run_result(name,args)
            self.assertFalse(result['executed'])
            self.assertIn(result['status'], ('not_executed','unavailable'))
        self.assertFalse(dry_run_result('other',{})['executed'])

    def test_instruction_forbids_claims(self):
        self.assertIn('Never assert an action started',TOOL_PROBE_INSTRUCTIONS)
        self.assertIn('text-only'.upper(), TOOL_PROBE_INSTRUCTIONS.upper())

    def test_host_never_forwards_probe_calls_to_core(self):
        src=(ROOT/'apps/desktop_alpha.py').read_text(encoding='utf-8')
        self.assertIn('if not self.config.tool_selection_probe:',src)
        self.assertIn('await relay.feed_event(event)',src)
        self.assertIn('probe_response_policy()',src)

    def test_renderer_never_publishes_audio(self):
        src=(ROOT/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
        self.assertIn('if (toolProbeRef.current)',src)
        self.assertIn("type === 'output_audio_buffer.started'",src)
        self.assertIn("audioRef.current.muted = true",src)
        self.assertIn("kind:'desktop_tool_probe'",src)
        self.assertIn("executed:false",src)

    def test_launcher_opt_in_and_default_unchanged(self):
        src=(ROOT/'scripts/realtime_ab.py').read_text(encoding='utf-8')
        for s in ('mini-tools','full-tools','mini-fast','full-fast', 'JARVIS_REALTIME_TOOL_SELECTION_PROBE'):
            self.assertIn(s,src)

if __name__=='__main__':unittest.main()
