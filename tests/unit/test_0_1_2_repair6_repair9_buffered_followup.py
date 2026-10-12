"""Focused regression for buffered tool follow-up completion and event ordering."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
APP=(ROOT/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')

class Repair9Tests(unittest.TestCase):
    def test_followup_budget_exceeds_previous_cap(self):
        self.assertIn("max_output_tokens:1024,output_modalities:['audio'],tools:[],tool_choice:'none'",APP)
        self.assertNotIn("max_output_tokens:384,output_modalities:['audio'],tools:[],tool_choice:'none'",APP)
    def test_followup_cannot_execute_tools(self):
        self.assertIn("executed:false",APP)
        self.assertIn("tools:[],tool_choice:'none'",APP)
        self.assertIn("No task was started and Luna did not actually run",APP)
    def test_drain_before_decision_is_remembered(self):
        self.assertIn("const bufferedOutputDrainedRef = useRef(false);",APP)
        self.assertIn("const finalizeBufferedIfReady = () =>",APP)
        self.assertIn("if (bufferedAudioSeenRef.current) finalizeBufferedIfReady()",APP)
        self.assertIn("bufferedOutputDrainedRef.current = true;",APP)
        self.assertIn("if (bufferedOutcomeRef.current === 'tool')",APP)
    def test_no_double_finalization(self):
        self.assertIn('bufferedFinalizeQueuedRef.current = true;',APP)
        self.assertIn('if (epoch === bufferedEpochRef.current',APP)
    def test_incomplete_reply_is_not_spoken_or_stuck(self):
        self.assertIn("source:'simulated_tool_failure'",APP)
        self.assertIn("setStateSafely('idle', 'Ready')",APP)
        self.assertIn("discardBufferedCapture();",APP)
        self.assertIn("if (event.response?.status !== 'completed'",APP)
    def test_feature_stays_opt_in(self):
        conf=(ROOT/'providers/voice_frontend/openai_realtime/config.py').read_text(encoding='utf-8')
        self.assertIn('JARVIS_REALTIME_BUFFERED_TOOL_PROBE',conf)
        launcher=(ROOT/'scripts/realtime_ab.py').read_text(encoding='utf-8')
        self.assertIn('mini-buffered',launcher)

if __name__=='__main__':unittest.main()
