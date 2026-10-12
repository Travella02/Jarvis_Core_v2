"""Repair8: sleep requires same-turn confirmed user text, not model evidence alone."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / 'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
HELPER = ROOT / 'apps/desktop/ui/src/sleepAuthorization.ts'

class SleepAuthorizerRuntime(unittest.TestCase):
    @unittest.skipUnless(shutil.which('tsc') and shutil.which('node'), 'TypeScript and Node not installed')
    def test_same_turn_audio_and_typed_authorization(self):
        with tempfile.TemporaryDirectory(prefix='jarvis_sleep_test_') as folder:
            process = subprocess.run([
                'tsc', '--target', 'es2022', '--module', 'commonjs', '--outDir', folder,
                str(HELPER)], capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            script = '''
const {isVerifiedSleepEvidence: yes,normalizeSleepWords: norm}=require(process.argv[1]);
const confirmed=(turn,binding,text,source='voice')=>({turn,binding,text,source});
const cases = [
  ["That's all", confirmed(7,'item_audio_7','Thanks Jarvis, that’s all.'),7,'item_audio_7','Jarvis',true],
  ['Go to sleep', confirmed(8,'item_audio_8','Go to sleep, Jarvis.'),8,'item_audio_8','Jarvis',true],
  ["that's all", confirmed(7,'item_audio_old','Thanks Jarvis, that’s all.'),7,'item_audio_7','Jarvis',false],
  ["that's all", confirmed(6,'item_audio_7','Thanks Jarvis, that’s all.'),7,'item_audio_7','Jarvis',false],
  ["that's all", null,7,'item_audio_7','Jarvis',false],
  ["that's all", confirmed(7,'item_audio_7','Thanks, Jarvis.'),7,'item_audio_7','Jarvis',false],
  ['Jarvis', confirmed(7,'item_audio_7','Jarvis'),7,'item_audio_7','Jarvis',false],
  ['bye',confirmed(7,'item_audio_7','Goodbye Jarvis'),7,'item_audio_7','Jarvis',false],
  ['bye',confirmed(7,'item_audio_7','Bye, Jarvis.'),7,'item_audio_7','Jarvis',true],
  ['goodbye',confirmed(7,'item_audio_7','Goodbye, Jarvis.'),7,'item_audio_7','Jarvis',true],
  ['stop',confirmed(7,'item_audio_7','Stop talking about sleep'),7,'item_audio_7','Jarvis',true],
  ["that's all",confirmed(7,'typed:7','Thanks Jarvis, thats all','typed'),7,'typed:7','Jarvis',true],
  ['good night',confirmed(7,'item_7','Good night Jarvis.'),7,'item_other','Jarvis',false],
  ['anything',confirmed(7,'item_7',''),7,'item_7','Jarvis',false],
];
let failed=[];
for (let i=0;i<cases.length;i++) {
  const [e,inp,t,b,w,expected]=cases[i];
  const actual=yes(e,inp,t,b,w);
  if(actual!==expected) failed.push({i,expected,actual});
}
console.log(JSON.stringify({failed,count:cases.length}));
if(failed.length) process.exit(1);
'''
            result = subprocess.run(['node', '-e', script, str(Path(folder) / 'sleepAuthorization.js')],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)['count'], 14)

class SleepIntegrationContracts(unittest.TestCase):
    def test_audio_sleep_waits_for_matching_item_transcription(self):
        event = APP.split("if (type === 'conversation.item.input_audio_transcription.completed')", 1)[1].split('// Experimental parallel text authority', 1)[0]
        self.assertIn('itemId === overlapInputBindingRef.current',event)
        self.assertIn('overlapActiveTurnRef.current',event)
        self.assertIn('settlePendingOverlapSleep()',event)
        self.assertIn('overlapTranscriptsRef.current.set(itemId,transcript)',event)
        self.assertIn('overlapSleepInputRef.current =',event)

    def test_sleep_tool_never_calls_enter_sleep_without_transcript_authorization(self):
        branch = APP.split("if (tool === 'sleep_jarvis')",1)[1].split('const realLuna =',1)[0]
        self.assertNotIn('enterSleep(',branch)
        self.assertIn('overlapPendingSleepRef.current =',branch)
        self.assertIn('phase:\'sleep_pending_confirmation\'',branch)
        self.assertIn('settlePendingOverlapSleep()',branch)
        self.assertIn('setTimeout(() => settlePendingOverlapSleep(true),2500)',branch)
        self.assertIn('overlapGateRef.current?.abort()',branch)
        self.assertIn("type:'output_audio_buffer.clear'",branch)

    def test_pending_sleep_settlement_validates_evidence_and_turn_epoch(self):
        settle=APP.split('const settlePendingOverlapSleep =',1)[1].split('const handleRealtimeEvent',1)[0]
        self.assertIn('isVerifiedSleepEvidence(',settle)
        self.assertIn('pending.turn !== overlapActiveTurnRef.current',settle)
        self.assertIn('pending.epoch !== overlapEpochRef.current',settle)
        self.assertIn("presenceRef.current !== 'awake'",settle)
        self.assertIn('overlapInputBindingRef.current',settle)
        self.assertIn('if (!confirmed && !timeout) return',settle)
        self.assertIn("phase:'sleep_rejected'",settle)
        self.assertIn("overlapDecisionRef.current = 'failed'",settle)
        self.assertIn("reason:'verified_user_sleep_request'",settle)
        self.assertIn("void enterSleep('voice_command')",settle)

    def test_supersession_and_sleep_cancel_pending_timer(self):
        cancel=APP.split('const cancelOverlap = () => {',1)[1].split('const silenceRealtimeOutput',1)[0]
        self.assertIn('window.clearTimeout(overlapSleepTimerRef.current)',cancel)
        self.assertIn('overlapPendingSleepRef.current = null',cancel)
        self.assertIn('overlapInputBindingRef.current =',cancel)
        self.assertIn('overlapSleepInputRef.current = null',cancel)
        self.assertIn('overlapEpochRef.current += 1',cancel)
        self.assertIn('cancelOverlap(); // A typed turn replaces',APP)
        self.assertIn('if (overlapProbeRef.current) cancelOverlap();',APP)
        self.assertIn('silenceRealtimeOutput();',APP.split('const enterSleep = async',1)[1].split('const requestNormalRealtimeResponse',1)[0])

    def test_cancelled_candidate_errors_cannot_poison_sleep_state(self):
        error_branch=APP.split("if (type === 'error') {\n        // A cancelled private candidate",1)[1].split('// Experimental audio publication gate',1)[0]
        self.assertIn('overlapPendingSleepRef.current',error_branch)
        self.assertIn('!overlapActiveTurnRef.current',error_branch)
        self.assertIn("presenceRef.current !== 'awake'",error_branch)
        self.assertIn("overlapDecisionRef.current === 'failed'",error_branch)
        self.assertIn("phase:'cancellation_error_ignored'",error_branch)

    def test_regular_direct_luna_audio_pipeline_unchanged(self):
        selection=APP.split('const requestOverlapResponses =',1)[1].split('const awaitOverlapAudioCommit =',1)[0]
        self.assertIn("output_modalities:['audio'],max_output_tokens:1024",selection)
        self.assertIn("metadata:{jarvis_stage:'overlap_decision'",selection)
        self.assertIn("metadata:{jarvis_stage:'overlap_candidate'",selection)
        self.assertIn('requestOverlapResponses(dc, \'\', clean)',APP)
        self.assertIn('ask_luna',selection)

if __name__ == '__main__': unittest.main()
