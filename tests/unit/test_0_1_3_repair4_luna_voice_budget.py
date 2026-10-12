"""0.1.3 Repair4 regression: Core voice synthesis budget and recoverable failure."""
from pathlib import Path
import re
import unittest
ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
HOST = (ROOT/'apps/desktop_alpha.py').read_text(encoding='utf-8')

class Repair4Contracts(unittest.TestCase):
    def test_long_core_result_not_limited_to_speculative_token_budget(self):
        section = APP.split('const speakCoreLunaResult =',1)[1].split('const handleRealtimeEvent =',1)[0]
        self.assertIn("max_output_tokens:'inf'",section)
        self.assertNotIn('max_output_tokens:1024',section)
        self.assertIn("jarvis_stage:'core_luna_voice'",section)
        self.assertIn("conversation:'none'",section)
    def test_short_speculative_candidate_is_unchanged(self):
        section=APP.split('const requestOverlapResponses =',1)[1].split('const awaitOverlapAudioCommit',1)[0]
        self.assertIn("output_modalities:['audio'],max_output_tokens:1024",section)
    def test_core_fallback_keeps_session_awake_and_verified_text_readable(self):
        section=APP.split('const fallbackCoreLunaVoice =',1)[1].split('const speakCoreLunaResult =',1)[0]
        self.assertIn("overlapGateRef.current?.abort();",section)
        self.assertIn("setCaption(verifiedText",section)
        self.assertIn("setStateSafely('idle'",section)
        self.assertNotIn("setStateSafely('error'",section)
        self.assertNotIn('enterSleep(',section)
        self.assertIn("voice_delivered:false",section)
    def test_incomplete_and_audio_errors_use_fallback(self):
        section=APP.split("if (responseId === overlapCandidateIdRef.current && stage === overlapCandidateStageRef.current)",1)[1]
        self.assertIn("fallbackCoreLunaVoice(turn,reason)",section)
        self.assertIn("if (!fallbackCoreLunaVoice(turn,reason))",section)
        self.assertIn("fallbackCoreLunaVoice(turn,'pcm_unavailable')",APP)
        self.assertIn("fallbackCoreLunaVoice(turn,'remote_stream_unavailable')",APP)
    def test_no_partial_core_caption_claim(self):
        self.assertIn("overlapCandidateStageRef.current !== 'core_luna_voice'",APP)
        self.assertIn("phase:'synthesis_completed',status:'completed'",APP)
    def test_cancel_clears_core_text_and_stale_turns_cannot_fallback(self):
        section=APP.split('const cancelOverlap =',1)[1].split('const silenceRealtimeOutput =',1)[0]
        self.assertIn("coreLunaVerifiedTextRef.current = ''",section)
        fallback=APP.split('const fallbackCoreLunaVoice =',1)[1].split('const speakCoreLunaResult =',1)[0]
        self.assertIn("turn !== overlapActiveTurnRef.current",fallback)
        self.assertIn("presenceRef.current !== 'awake'",fallback)
    def test_host_can_trace_recovery_without_claiming_spoken_success(self):
        self.assertIn('if kind == "desktop_luna_voice":',HOST)
        self.assertIn('[Jarvis Luna Voice]',HOST)

if __name__ == '__main__':
    unittest.main()
