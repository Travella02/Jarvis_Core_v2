"""Regression: text-only tool probe must not intercept provider VAD lifecycle."""
from pathlib import Path
import unittest

APP=(Path(__file__).resolve().parents[2]/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')

class ProbeVadLifecycleTests(unittest.TestCase):
    def test_probe_interception_excludes_both_vad_events(self):
        self.assertIn("if (toolProbeRef.current && type !== 'input_audio_buffer.speech_started' && type !== 'input_audio_buffer.speech_stopped')", APP)

    def test_vad_events_reach_shared_turn_lifecycle(self):
        probe=APP.index("if (toolProbeRef.current && type !== 'input_audio_buffer.speech_started'")
        shared=APP.index("if (type === 'input_audio_buffer.speech_started')",probe)
        block=APP[shared:APP.index("} else if (type === 'response.created')",shared)]
        self.assertIn('turnCounterRef.current += 1', block)
        self.assertIn("type === 'input_audio_buffer.speech_stopped'", block)
        self.assertIn('requestNormalRealtimeResponse();', block)
        self.assertIn("latencyRef.current.route = 'tool_probe'",block)

    def test_probe_responses_still_not_forwarded_to_core(self):
        probe=APP.index("if (toolProbeRef.current && type !== 'input_audio_buffer.speech_started'")
        core=APP.index('forwardToCore(event);',probe)
        intercepted=APP[probe:core]
        self.assertIn("if (type === 'response.done')",intercepted)
        self.assertIn("if (type === 'response.created')",intercepted)
        self.assertIn("return;",intercepted)
        self.assertIn("audioRef.current.muted = true",intercepted)
        self.assertIn("executed:false",intercepted)
        self.assertIn("type:'function_call_output'",intercepted)

    def test_single_manual_response_creation_policy(self):
        shared=APP.index("if (type === 'input_audio_buffer.speech_started')")
        stop=APP.index("} else if (type === 'response.created')",shared)
        block=APP[shared:stop]
        self.assertEqual(block.count('requestNormalRealtimeResponse();'),1)
        self.assertIn('auto_create_response=False', (Path(__file__).resolve().parents[2]/'apps/desktop_alpha.py').read_text(encoding='utf-8'))

if __name__=='__main__':
    unittest.main()
