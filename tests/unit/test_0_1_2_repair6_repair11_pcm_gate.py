"""Repair11: PCM gate is isolated, continuous and fails closed.
The Node test executes the actual processor logic without a real sound device.
"""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / 'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
GATE = (ROOT / 'apps/desktop/ui/src/streamingPcmGate.ts').read_text(encoding='utf-8')
WORKLET = ROOT / 'apps/desktop/ui/src/pcmGateProcessor.js'

class Repair11PcmTests(unittest.TestCase):
    def test_pcm_gate_is_used_instead_of_opus_segment_stitching(self):
        self.assertIn("from './streamingPcmGate'", APP)
        self.assertIn('StreamingPcmGate.create(stream', APP)
        self.assertNotIn('new StreamingOpusGate(', APP)
        self.assertIn("new URL('./pcmGateProcessor.js', import.meta.url)", GATE)
        self.assertNotIn('MediaRecorder', GATE)
        self.assertNotIn('MediaSource', GATE)

    def test_audio_only_after_trusted_decision(self):
        self.assertIn("overlapDecisionRef.current = calls.length ? 'tool' : 'direct'", APP)
        self.assertIn("if (overlapDecisionRef.current === 'direct' && overlapDirectVerifiedRef.current) gate.authorize()", APP)
        self.assertIn('overlapGateRef.current?.abort()', APP)
        self.assertIn('audioRef.current.muted = true', APP)
        self.assertIn("tools:[],tool_choice:'none'", APP)
        self.assertIn("No tool or action was executed.", APP)
        self.assertIn("this.gate?.port.postMessage({type:'authorize'})", GATE)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is unavailable')
    def test_worklet_outputs_only_zeros_until_authorized_and_samples_stay_continuous(self):
        test_js = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
let Processor;
class AudioWorkletProcessor { constructor(){ this.port = {onmessage:null, postMessage:msg=>events.push(msg)}; } }
const events=[];
const sandbox={AudioWorkletProcessor,Float32Array,Math,sampleRate:48000,
  registerProcessor:(name,cls)=>{assert.equal(name,'jarvis-pcm-gate');Processor=cls;}};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),sandbox);
const proc = new Processor({processorOptions:{rate:48000}});
function tick(signal=0.1, n=128){
  const input=[new Float32Array(n).fill(signal)];
  const output=[new Float32Array(n),new Float32Array(n)];
  proc.process([input],[output]);
  return output[0];
}
for(let i=0;i<24;i++) assert(tick().every(x=>x===0),'preauth audio leaked');
proc.port.onmessage({data:{type:'authorize'}});
let heard=false, last=0, jumps=0;
for(let i=0;i<24;i++) for(const value of tick()) {
  if(value!==0) {heard=true; if(last!==0 && Math.abs(value-last)>0.02) jumps++; last=value; }
}
assert(heard,'authorized PCM did not play');
assert.equal(jumps,0,'PCM boundary discontinuity');
assert(events.some(x=>x.type==='playing'));
proc.port.onmessage({data:{type:'finish'}});
for(let i=0;i<100;i++) tick(0.1);
assert(events.some(x=>x.type==='ended'),'finish did not drain');
const later=tick();assert(later.every(x=>x===0),'played after finish');
const cancelled=new Processor({processorOptions:{rate:48000}});
for(let i=0;i<15;i++) cancelled.process([[new Float32Array(128).fill(.1)]],[[new Float32Array(128)]]);
cancelled.port.onmessage({data:{type:'abort'}});
cancelled.port.onmessage({data:{type:'authorize'}});
const post=[new Float32Array(128)];cancelled.process([[new Float32Array(128).fill(.1)]],[post]);
assert(post[0].every(x=>x===0),'cancelled worklet leaked samples');
'''
        done = subprocess.run(['node', '-e', test_js, str(WORKLET)], text=True, capture_output=True, timeout=15)
        self.assertEqual(done.returncode, 0, done.stderr)
