"""Repair13: opt-in PCM onset trim must be sample-safe, authority-safe and testable offline."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts import realtime_ab

ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / 'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
GATE = (ROOT / 'apps/desktop/ui/src/streamingPcmGate.ts').read_text(encoding='utf-8')
WORKLET = (ROOT / 'apps/desktop/ui/src/pcmGateProcessor.js').read_text(encoding='utf-8')
HOST = (ROOT / 'apps/desktop_alpha.py').read_text(encoding='utf-8')

class PcmOnsetTests(unittest.TestCase):
    def test_baseline_and_trim_have_only_one_environment_difference(self):
        modes = []
        def fake_call(command, *, cwd, env, shell):
            modes.append({k:v for k,v in env.items() if k.startswith('JARVIS_')})
            return 0
        for mode in ('mini-overlap-luna', 'mini-overlap-luna-trim'):
            with mock.patch('sys.argv',['realtime_ab.py',mode]),mock.patch.object(realtime_ab.subprocess,'call',side_effect=fake_call):
                self.assertEqual(realtime_ab.main(),0)
        baseline, trim = modes
        self.assertEqual(baseline['JARVIS_PCM_TRIM_LEADING_SILENCE'],'0')
        self.assertEqual(trim['JARVIS_PCM_TRIM_LEADING_SILENCE'],'1')
        self.assertEqual({k:v for k,v in baseline.items() if k != 'JARVIS_PCM_TRIM_LEADING_SILENCE'},
                         {k:v for k,v in trim.items() if k != 'JARVIS_PCM_TRIM_LEADING_SILENCE'})
        self.assertEqual(trim['JARVIS_CORE_LUNA_PROBE'],'1')
        self.assertEqual(trim['JARVIS_DECISIONS_SHADOW_PROBE'],'0')

    def test_protects_core_authority_and_sleep(self):
        self.assertIn("overlapDecisionRef.current === 'direct' && overlapDirectVerifiedRef.current", APP)
        self.assertIn('if (!input || input.turn !== overlapActiveTurnRef.current',APP)
        self.assertIn("phase:'sleep_evidence_check'",APP)
        self.assertIn('overlapGateRef.current?.abort()',APP)
        self.assertIn('if (!this.approved) return true;',WORKLET)
        self.assertIn("case 'abort':",WORKLET)
        self.assertIn('output_modalities:[\'audio\'],max_output_tokens:1024,tools:[],tool_choice:',APP)
        self.assertIn('trimLeadingSilence = false',GATE)
        self.assertIn('pcm_trim_leading_silence', HOST)

    def test_telemetry_separates_actual_provider_pcm_from_authorization(self):
        for field in ('pcm_signal_ms','pcm_buffer_ready_ms','pcm_trim_enabled',
                      'signal_to_first_audio_ms','authorized_to_first_audio_ms'):
            self.assertIn(field, APP)
            self.assertIn(f'"{field}"', HOST)
        self.assertIn("this.port.postMessage({type:'first_pcm_signal'})",WORKLET)
        self.assertIn("this.port.postMessage({type:'pcm_buffer_ready'})",WORKLET)

    def test_comparison_report_excludes_wake_and_uses_actual_pcm(self):
        from scripts.repair13_latency_report import parse_log, summary
        baseline = """[Jarvis Overlap] turn=1 | phase=direct | decision_ms=500
[Jarvis Latency Detail] turn=1 | route_ms=600 | first_audio_ms=3000 | pcm_signal_ms=1200 | pcm_trim_enabled=false
[Jarvis Overlap] turn=2 | phase=direct | decision_ms=500
[Jarvis Latency Detail] turn=2 | route_ms=550 | first_audio_ms=1200 | pcm_signal_ms=900 | pcm_buffer_ready_ms=960 | gate_authorized_ms=550 | authorized_to_first_audio_ms=650 | pcm_trim_enabled=false
[Jarvis Overlap] turn=3 | phase=sleep | decision_ms=750
[Jarvis Latency Detail] turn=3 | first_audio_ms=2000
"""
        report=summary(parse_log(baseline))
        self.assertEqual(report['n'],1)
        self.assertEqual(report['first_audio_ms_median'],1200)
        self.assertEqual(report['pcm_signal_ms_median'],900)
        self.assertEqual(report['authorized_to_first_audio_ms_median'],650)

    @unittest.skipUnless(shutil.which('node'),'Node needed for sample-level worklet tests')
    def test_worklet_sample_level_safety_and_latency(self):
        script = r'''
const fs=require('fs'),vm=require('vm');
let Klass;
class AP {constructor(){const ports=[];this.port={postMessage:(m)=>ports.push(m),onmessage:null};this.messages=ports;}}
const sandbox={AudioWorkletProcessor:AP, Float32Array,Math,Number,
  sampleRate:48000,registerProcessor:(name,k)=>{Klass=k}};
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),sandbox);
const checks=[];
function ensure(ok,label){if(!ok)throw Error(label);checks.push(label);}
function processor(trim){const p=new Klass({processorOptions:{rate:48000,trimLeadingSilence:trim}});return p;}
function step(p,amp=0){const a=new Float32Array(128);a.fill(amp);const out=[new Float32Array(128),new Float32Array(128)];p.process([[a]],[out]);return out[0].some(x=>Math.abs(x)>0.0006);}
function run(trim){
 const p=processor(trim); let audibleBeforeAuth=false;
 for(let n=0;n<80;n++)audibleBeforeAuth ||=step(p,0);
 for(let n=0;n<10;n++)audibleBeforeAuth ||=step(p,0.3);
 ensure(!audibleBeforeAuth,'never audible before authorization '+trim);
 const queueAtAuthorize=p.count;
 p.port.onmessage({data:{type:'authorize'}});
 let first=-1;
 for(let n=0;n<140;n++){if(step(p,0.3)&&first<0)first=n;}
 const signals=p.messages.filter(m=>m.type==='first_pcm_signal');
 const ready=p.messages.filter(m=>m.type==='pcm_buffer_ready');
 ensure(signals.length===1,'one actual-signal timestamp '+trim);
 ensure(ready.length===1,'one audio-buffer-ready timestamp '+trim);
 ensure(first>=0,'playback after authorization '+trim);
 p.port.onmessage({data:{type:'abort'}});
 ensure(p.cancelled&&!step(p,.3),'abort permanently silences '+trim);
 return {queueAtAuthorize,first};
}
const old=run(false),trim=run(true);
ensure(old.queueAtAuthorize>9000,'baseline queues all leading silence');
ensure(trim.queueAtAuthorize<2500,'trim mode discards silent pre-roll');
ensure(trim.first+20<old.first,'trim audio begins at least 20 blocks earlier in simulation');
const onlySilence=processor(true);
for(let n=0;n<80;n++)step(onlySilence,0);
ensure(onlySilence.count===0,'all-zero track never fills private gate');
onlySilence.port.onmessage({data:{type:'authorize'}});
ensure(!step(onlySilence,0),'authorization of silent track remains silent');
const pause=processor(true);
for(let n=0;n<25;n++)step(pause,.2);
const beforePause=pause.count;
for(let n=0;n<20;n++)step(pause,0);
ensure(pause.count===beforePause+20*128,'later speech pauses are retained unchanged');
console.log(JSON.stringify({old,trim,checks:checks.length}));
'''
        with tempfile.TemporaryDirectory(prefix='jarvis_repair13_pcm_') as t:
            runner=Path(t)/'run.cjs';runner.write_text(script,encoding='utf-8')
            result=subprocess.run(['node',str(runner),str(ROOT/'apps/desktop/ui/src/pcmGateProcessor.js')],
                                  capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
            data=json.loads(result.stdout)
            self.assertLess(data['trim']['first'],data['old']['first'])

if __name__ == '__main__':unittest.main()
