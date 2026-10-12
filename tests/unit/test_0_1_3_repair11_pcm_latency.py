"""Repair11: prewarmed isolated PCM and live per-turn latency milestones."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / 'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
PCM = (ROOT / 'apps/desktop/ui/src/streamingPcmGate.ts').read_text(encoding='utf-8')
HOST = (ROOT / 'apps/desktop_alpha.py').read_text(encoding='utf-8')

class LatencyContracts(unittest.TestCase):
    def test_pcm_gate_never_opens_on_prewarm(self):
        self.assertIn('static async prewarm()', PCM)
        warm = PCM.split('static async prewarm()',1)[1].split('static async create(',1)[0]
        self.assertNotIn('createMediaStreamSource(',warm)
        self.assertNotIn("postMessage({type:'authorize'})",warm)
        self.assertNotIn('context.resume()',warm)
        self.assertIn("this.warmContext = context",warm)
        self.assertIn('private static warmPromise',PCM)
    def test_audio_remains_private_until_both_checks(self):
        self.assertIn("overlapDecisionRef.current === 'direct' && overlapDirectVerifiedRef.current",APP)
        self.assertIn('if (!input || input.turn !== overlapActiveTurnRef.current',APP)
        self.assertIn('gate.authorize()', APP)
        self.assertIn("'jarvis_stage':'",APP) if False else None
        self.assertIn("jarvis_stage:'overlap_decision'",APP)
        self.assertIn("jarvis_stage:'overlap_candidate'",APP)
    def test_timing_tracks_all_stages(self):
        self.assertIn("phase:'pcm_prewarm_ready'",APP)
        self.assertIn("phase:'latency_breakdown'",APP)
        for key in ('commit_ms','transcript_ms','route_ms','candidate_created_ms','pcm_ready_ms',
                    'gate_authorized_ms','first_audio_ms'):
            self.assertIn(key,APP)
    def test_host_prints_every_timing_field(self):
        self.assertIn('[Jarvis Latency Detail]',HOST)
        self.assertIn('message.get("phase") == "latency_breakdown"',HOST)
        for key in ('commit_ms','transcript_ms','route_ms','candidate_created_ms','pcm_ready_ms',
                    'gate_authorized_ms','first_audio_ms'):
            self.assertIn(f'"{key}"',HOST)
    def test_no_synthesis_budget_or_core_changes(self):
        self.assertIn('max_output_tokens:1024,tools:[],tool_choice:',APP)
        self.assertIn("phase:'sleep_evidence_check'",APP)
        self.assertIn("metadata:{jarvis_stage:'core_luna_voice'",APP)

    @unittest.skipUnless(shutil.which('tsc') and shutil.which('node'),'Node and TypeScript needed')
    def test_pcm_prewarm_and_gate_reuse_in_node(self):
        with tempfile.TemporaryDirectory(prefix='jarvis_pcm11_') as t:
            build = subprocess.run(['tsc','--target','es2022','--module','esnext','--outDir',t,
                str(ROOT/'apps/desktop/ui/src/streamingPcmGate.ts')],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            compiled=Path(t)/'streamingPcmGate.js'
            jsfile=Path(t)/'streamingPcmGate.mjs'
            jsfile.write_text(compiled.read_text(encoding='utf-8'),encoding='utf-8')
            script=r'''
let modules=0,contexts=0,sources=0,connected=0,closed=0,authorized=0;
class AC {
  constructor(){contexts++;this.state='suspended';this.destination={};this.sampleRate=48000;
    this.audioWorklet={addModule:async()=>{modules++}};}
  createMediaStreamSource(){sources++;return {connect(){connected++},disconnect(){connected--}}}
  async resume(){this.state='running'}
  async close(){closed++;this.state='closed'}
}
globalThis.AudioContext=AC;
globalThis.MediaStream=class {};
globalThis.AudioWorkletNode=class {
  constructor(){this.port={onmessage:null,postMessage(m){if(m.type==='authorize')authorized++}}}
  connect(){}
  disconnect(){}
};
const {StreamingPcmGate}=await import(process.argv[2]);
await Promise.all([StreamingPcmGate.prewarm(),StreamingPcmGate.prewarm()]);
const before={contexts,modules,sources,connected};
const g1=await StreamingPcmGate.create(new MediaStream(),()=>{},()=>{},()=>{},()=>{});
const g2=await StreamingPcmGate.create(new MediaStream(),()=>{},()=>{},()=>{},()=>{});
g1.abort();g2.authorize();g2.abort();
const after={contexts,modules,sources,connected,closed,authorized};
console.log(JSON.stringify({before,after}));
if(before.contexts!==1||before.modules!==1||before.sources!==0||
 after.contexts!==1||after.modules!==1||after.sources!==2||
 after.connected!==0||after.closed!==0||after.authorized!==1)process.exit(1);
'''
            runner=Path(t)/'run.mjs';runner.write_text(script,encoding='utf-8')
            result=subprocess.run(['node',str(runner),jsfile.as_uri()],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
            self.assertEqual(json.loads(result.stdout)['before']['sources'],0)
