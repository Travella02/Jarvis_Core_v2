"""Opt-in, fail-closed buffered Realtime Mini tool-selection experiment."""
import unittest
from pathlib import Path

from providers.voice_frontend.openai_realtime.config import OpenAIRealtimeConfig
from providers.voice_frontend.openai_realtime.webrtc import build_realtime_session
from providers.voice_frontend.openai_realtime.tool_probe import ALLOWED_PROBE_TOOLS

ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / 'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
SERVER = (ROOT / 'apps/desktop_alpha.py').read_text(encoding='utf-8')
LAUNCHER = (ROOT / 'scripts/realtime_ab.py').read_text(encoding='utf-8')


class BufferedVoiceExperimentTests(unittest.TestCase):
    def test_off_by_default(self):
        c=OpenAIRealtimeConfig.from_env(env={})
        self.assertFalse(c.buffered_tool_probe)
        self.assertEqual(c.model, 'gpt-realtime-2.1-mini')

    def test_feature_flag_is_explicit(self):
        c=OpenAIRealtimeConfig.from_env(env={'JARVIS_REALTIME_BUFFERED_TOOL_PROBE':'1'})
        self.assertTrue(c.buffered_tool_probe)
        with self.assertRaises(ValueError):
            OpenAIRealtimeConfig.from_env(env={'JARVIS_REALTIME_BUFFERED_TOOL_PROBE':'invalid'})

    def test_server_session_audio_and_tools_can_be_selected(self):
        c=OpenAIRealtimeConfig.from_env(env={'JARVIS_REALTIME_BUFFERED_TOOL_PROBE':'1'})
        session=build_realtime_session(c,auto_create_response=False)
        self.assertEqual(session['output_modalities'], ['audio'])
        self.assertEqual({tool['name'] for tool in session['tools']},set(ALLOWED_PROBE_TOOLS))
        self.assertEqual(session['tool_choice'],'auto')

    def test_normal_modes_unchanged(self):
        for env in ({},{'JARVIS_REALTIME_DIRECT_ONLY_BENCHMARK':'1'}):
            c=OpenAIRealtimeConfig.from_env(env=env)
            self.assertFalse(c.buffered_tool_probe)
            self.assertEqual(build_realtime_session(c,auto_create_response=False)['output_modalities'],['audio'])

    def test_mini_only_buffered_launcher_and_separate_flags(self):
        self.assertIn('"mini-buffered": ("gpt-realtime-2.1-mini", False)',LAUNCHER)
        self.assertIn('JARVIS_REALTIME_BUFFERED_TOOL_PROBE',LAUNCHER)
        self.assertIn('JARVIS_REALTIME_TOOL_SELECTION_PROBE',LAUNCHER)
        self.assertIn('JARVIS_PARALLEL_SHADOW_PROBE',LAUNCHER)

    def test_web_rtc_track_never_unmuted_during_buffered_probe(self):
        self.assertIn('audioRef.current.muted = true; // Fail closed until',APP)
        self.assertIn('bufferedRemoteStreamRef.current = remote',APP)
        self.assertIn('new MediaRecorder(stream',APP)
        self.assertIn('resetBufferedTurn();',APP)
        self.assertIn("if (bufferedToolProbeRef.current && type !== 'input_audio_buffer.speech_started'",APP)

    def test_publication_requires_response_completed_and_no_tool(self):
        self.assertIn("event.response?.status !== 'completed'",APP)
        self.assertIn("const calls = (event.response?.output || []).filter",APP)
        self.assertIn("bufferedOutcomeRef.current = 'approved'",APP)
        self.assertIn("if (bufferedOutcomeRef.current === 'approved')",APP)
        self.assertIn('completeBufferedCapture(true)',APP)
        self.assertIn('if (!approved || !chunks.length',APP)

    def test_pretool_audio_is_discarded_and_post_tool_is_read_only(self):
        self.assertIn("bufferedOutcomeRef.current = 'tool'",APP)
        self.assertIn("discardBufferedCapture();",APP)
        self.assertIn("pretool_audio_not_authorized",APP)
        self.assertIn("name === 'ask_luna' || name === 'test_action'",APP)
        self.assertIn("executed:false",APP)
        self.assertIn("tools:[],tool_choice:'none'",APP)
        self.assertIn("bufferedFollowupNextRef.current = true",APP)

    def test_backend_logs_usage_but_never_forwards_probe_calls_to_executor(self):
        self.assertIn('if not self.config.buffered_tool_probe:', SERVER)
        self.assertIn('desktop_buffered_audio', SERVER)
        self.assertIn("sendControlMessage({kind:'realtime_event',event}); // Billing only", APP)
        self.assertIn('response.done',APP)

    def test_interruption_and_memory_bounds(self):
        self.assertIn("if (bufferedToolProbeRef.current) resetBufferedTurn();",APP)
        self.assertIn('30000',APP)
        self.assertIn('URL.revokeObjectURL(bufferedPlaybackUrlRef.current)',APP)
        self.assertIn('bufferedEpochRef.current += 1',APP)

if __name__=='__main__':unittest.main()
