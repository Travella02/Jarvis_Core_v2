"""Repair9: validate model citations against bound user utterances and guard unconfirmed audio."""
from __future__ import annotations
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / 'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
HELPER = ROOT / 'apps/desktop/ui/src/sleepAuthorization.ts'


class MatcherRuntime(unittest.TestCase):
    @unittest.skipUnless(shutil.which('tsc') and shutil.which('node'), 'Node/TypeScript unavailable')
    def test_flexible_quote_matching_but_never_wrong_turn_or_gratitude(self):
        with tempfile.TemporaryDirectory(prefix='repair9_sleep_') as tmp:
            compile_result = subprocess.run(['tsc','--target','es2022','--module','commonjs',
                '--outDir',tmp,str(HELPER)],capture_output=True,text=True)
            self.assertEqual(compile_result.returncode,0,compile_result.stderr)
            js = r'''
const m=require(process.argv[1]);
const inp=(s,b='item_9',t=9)=>({source:'voice',text:s,binding:b,turn:t});
const yes=(quote,text,b='item_9',turn=9)=>m.isVerifiedSleepEvidence(quote,inp(text,b,turn),9,'item_9','Jarvis');
const cases=[
  ["That's all, Jarvis", "That's all Jarvis",true],
  ["That's all, I'm done", "That's all Jarvis",true],
  ["That's all", "Thanks Jarvis, that's all",true],
  ["I'd like to go to sleep", "Go to sleep Jarvis",true],
  ["Goodbye", "Goodbye Jarvis",true],
  ["Thanks Jarvis, that's all", "Thanks Jarvis",false],
  ["That's all", "What does that's all mean?",true], // Semantic intent stays the model's responsibility.
  ["Go to sleep", "Do not go to sleep Jarvis",false],
  ["Don't go to sleep", "Go to sleep Jarvis",false],
  ["That's all", "Jarvis",false],
  ["bye", "goodbye Jarvis",false],
  ["that's all", "",false],
  ["that's all", "uh oh",false],
];
let failed=[];
cases.forEach(([q,s,expected],i)=>{if(yes(q,s)!==expected)failed.push(i)});
if(yes("that's all","that's all Jarvis",'item_old'))failed.push('binding');
if(yes("that's all","that's all Jarvis",'item_9',8))failed.push('turn');
const speech=[['uh oh',false],['',false],['the',false],['Jarvis',true],['Thanks Jarvis',true],['hi',false],['what is 2 plus 2',true]];
speech.forEach(([s,expected],i)=>{if(m.hasSubstantiveUserWords(s)!==expected)failed.push('speech'+i)});
console.log(JSON.stringify({failed,cases:cases.length,speech:speech.length}));
if(failed.length)process.exit(1);
'''
            out = subprocess.run(['node','-e',js,str(Path(tmp)/'sleepAuthorization.js')],
                                 capture_output=True,text=True)
            self.assertEqual(out.returncode,0,out.stdout+out.stderr)
            self.assertEqual(json.loads(out.stdout)['cases'],13)


class SourceContracts(unittest.TestCase):
    def test_sleep_diagnostics_and_protected_decision(self):
        settlement = APP.split('const settlePendingOverlapSleep =',1)[1].split('const handleRealtimeEvent',1)[0]
        self.assertIn('isVerifiedSleepEvidence(',settlement)
        self.assertIn("phase:'sleep_evidence_check'",settlement)
        self.assertIn('same_binding:',settlement)
        self.assertIn('pending.epoch !== overlapEpochRef.current',settlement)
        self.assertIn("reason:'verified_user_sleep_request'",settlement)

    def test_unconfirmed_direct_audio_stays_private(self):
        self.assertIn('const settlePendingOverlapDirect =',APP)
        self.assertIn('const rejectUnconfirmedDirect =',APP)
        self.assertIn("phase:'unconfirmed_direct_discarded'",APP)
        self.assertIn('hasSubstantiveUserWords(input.text)',APP)
        self.assertIn('input.binding !== overlapInputBindingRef.current',APP)
        self.assertIn("if (overlapDecisionRef.current === 'direct' && overlapDirectVerifiedRef.current) gate.authorize()",APP)
        self.assertIn('settlePendingOverlapDirect();',APP)
        self.assertIn('rejectUnconfirmedDirect(turn,epoch)',APP)
        self.assertIn('overlapGateRef.current?.abort();',APP)

    def test_new_turn_sleep_and_luna_not_changed(self):
        self.assertIn("metadata:{jarvis_stage:'core_luna_voice'",APP)
        self.assertIn('requestOverlapResponses(dc, \'\', clean)',APP)
        self.assertIn("phase:'sleep_pending_confirmation'",APP)
        self.assertIn('window.clearTimeout(overlapDirectTimerRef.current)',APP)
        self.assertIn("text:`Jarvis Core returned",APP)

if __name__ == '__main__': unittest.main()
