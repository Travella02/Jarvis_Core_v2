"""Repair10 safety invariants for parallel authority with streamed private audio."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
GATE = (ROOT/'apps/desktop/ui/src/streamingOpusGate.ts').read_text(encoding='utf-8')
LAUNCHER = (ROOT/'scripts/realtime_ab.py').read_text(encoding='utf-8')
CONFIG = (ROOT/'providers/voice_frontend/openai_realtime/config.py').read_text(encoding='utf-8')
SERVER = (ROOT/'apps/desktop_alpha.py').read_text(encoding='utf-8')
WEBRTC = (ROOT/'providers/voice_frontend/openai_realtime/webrtc.py').read_text(encoding='utf-8')

class ParallelStreamTests(unittest.TestCase):
    def test_mode_explicitly_opt_in(self):
        self.assertIn('overlap_probe: bool = False', CONFIG)
        self.assertIn('JARVIS_REALTIME_OVERLAP_PROBE', CONFIG)
        self.assertIn('"mini-overlap"', LAUNCHER)
        self.assertIn('"JARVIS_PARALLEL_SHADOW_PROBE"] = "0"', LAUNCHER)

    def test_server_disables_real_core_execution(self):
        self.assertIn('if not self.config.overlap_probe:', SERVER)
        self.assertIn('overlap_probe_response_policy() if overlap_probe', SERVER)
        self.assertIn('probe_response_policy() if tool_probe', SERVER)
        self.assertIn('"overlap_probe": overlap_probe', SERVER)

    def test_webrtc_default_session_is_text_only(self):
        self.assertIn('config.tool_selection_probe or config.overlap_probe else ["audio"]', WEBRTC)

    def test_parallel_response_scope_and_tools(self):
        self.assertEqual(APP.count("conversation:'none'"), 3)  # opt-in real-Core voice follow-up is isolated too
        self.assertIn("metadata:{jarvis_stage:'overlap_decision'", APP)
        self.assertIn("metadata:{jarvis_stage:'overlap_candidate'", APP)
        self.assertIn("output_modalities:['text'],max_output_tokens:512,tools,tool_choice:'auto'", APP)
        self.assertIn("output_modalities:['audio'],max_output_tokens:1024,tools:[],tool_choice:'none'", APP)

    def test_only_decision_authorizes_private_speech(self):
        self.assertIn("overlapDecisionRef.current = calls.length ? 'tool' : 'direct'", APP)
        self.assertIn("if (overlapDecisionRef.current === 'direct')", APP)
        self.assertIn('overlapGateRef.current?.authorize()', APP)
        self.assertIn('overlapGateRef.current?.abort()', APP)
        self.assertIn("audioRef.current.muted = true", APP)

    def test_no_tool_execution_or_fake_success(self):
        self.assertIn('dry_run:!realLuna,executed:false', APP)  # original probe is dry-run; opt-in Luna differs
        self.assertIn('No tool or action was executed.', APP)
        self.assertIn('Never execute provider calls', (ROOT/'providers/voice_frontend/openai_realtime/tool_probe.py').read_text(encoding='utf-8'))

    def test_true_streaming_not_wait_for_end(self):
        self.assertIn('this.recorder.start(100)', GATE)
        self.assertIn("this.buffer.appendBuffer(this.waiting.shift()!)", GATE)
        self.assertIn("void this.player?.play()", GATE)
        self.assertIn('this.approved = true;', GATE)
        self.assertIn('else if (this.finished)', GATE)

    def test_provider_track_never_directly_unmutes(self):
        self.assertIn("if (audioRef.current) audioRef.current.muted = true;", APP)
        self.assertIn("if (overlapProbeRef.current && type !== 'input_audio_buffer.speech_started'", APP)

    def test_cancellation_bound_to_turn(self):
        self.assertIn('overlapEpochRef.current += 1;', APP)
        self.assertIn('const oldDone = overlapCandidateDoneRef.current;', APP)
        self.assertIn("type:'response.cancel',response_id:oldCandidate", APP)
        self.assertIn('if (overlapProbeRef.current) cancelOverlap();', APP)
        self.assertIn('if (epoch !== overlapEpochRef.current)', APP)

    def test_opus_requires_media_source_support(self):
        self.assertIn('MediaRecorder.isTypeSupported', GATE)
        self.assertIn('MediaSource.isTypeSupported', GATE)
        self.assertIn('private_audio_cap', GATE)
        self.assertIn('this.disposed = true;', GATE)

if __name__ == '__main__': unittest.main()
