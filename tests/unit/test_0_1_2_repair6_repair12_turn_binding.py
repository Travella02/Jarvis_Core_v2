"""Repair12: each overlapped response explicitly binds to the committed turn.

These are source-contract checks; real event ordering and WebRTC are still
subject to live Electron acceptance tests.
"""
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / 'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')

class OverlapTurnBindingTests(unittest.TestCase):
    def test_only_explicit_current_turn_input_for_both_responses(self):
        self.assertIn("? [{type:'item_reference',id:committedItemId}]", APP)
        self.assertIn("? [{type:'message',role:'user',content:[{type:'input_text',text:typedText.trim()}]}]", APP)
        self.assertEqual(APP.count("      input,\n      output_modalities:"), 2)
        self.assertIn("if (!input.length ||", APP)

    def test_speech_stopped_waits_for_commit(self):
        self.assertIn("if (overlapProbeRef.current) awaitOverlapAudioCommit();", APP)
        self.assertIn("type === 'input_audio_buffer.committed'", APP)
        self.assertIn("if (overlapAwaitingCommitRef.current) requestOverlapResponses(dcRef.current, itemId)", APP)
        self.assertNotIn("if (overlapProbeRef.current) requestOverlapResponses();", APP)

    def test_timeout_and_missing_commit_do_not_trigger_inference(self):
        self.assertIn("reason:'input_commit_timeout'", APP)
        self.assertIn("reason:'commit_missing_item_id'", APP)
        self.assertIn("}, 2000);", APP)
        self.assertIn("overlapCommitTimerRef.current = null;", APP)

    def test_stale_responses_cannot_claim_current_turn(self):
        self.assertIn("overlapActiveTurnRef.current = latencyRef.current.turn;", APP)
        self.assertEqual(APP.count("!== overlapActiveTurnRef.current || !overlapActiveTurnRef.current"), 2)
        self.assertIn("overlapEpochRef.current += 1;", APP)
        self.assertIn("overlapCommittedItemRef.current = '';", APP)
        self.assertIn('if (overlapProbeRef.current) cancelOverlap(); // A typed turn replaces', APP)

    def test_binding_telemetry_includes_commit_wait(self):
        SERVER = (ROOT / 'apps/desktop_alpha.py').read_text(encoding='utf-8')
        self.assertIn("input_binding={message.get('input_binding','n/a')}", SERVER)
        self.assertIn("commit_wait_ms={message.get('commit_wait_ms','n/a')}", SERVER)

    def test_pcm_path_untouched_and_tools_are_still_dry_run(self):
        self.assertIn("StreamingPcmGate.create(stream", APP)
        self.assertIn("tools:[],tool_choice:'none'", APP)
        self.assertIn("dry_run:true,executed:false", APP)
        self.assertIn("No tool or action was executed.", APP)

if __name__ == '__main__':
    unittest.main()
