/* Private, sample-continuous AudioWorklet gate for Jarvis overlap probe.
 * Provider audio enters only here, never through an audible HTML media element.
 * Zeros are emitted until the trusted turn decision explicitly authorizes audio.
 */
class JarvisPcmGateProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const rate = Number(options?.processorOptions?.rate || sampleRate);
    this.capacity = Math.max(16384, Math.round(rate * 8));
    this.ring = new Float32Array(this.capacity);
    this.read = 0;
    this.write = 0;
    this.count = 0;
    this.approved = false;
    this.finished = false;
    this.cancelled = false;
    this.started = false;
    this.notifiedPlaying = false;
    this.fadeSamples = Math.max(1, Math.round(rate * 0.007));
    this.playedSamples = 0;
    this.underflows = 0;
    this.startBuffer = Math.max(256, Math.round(rate * 0.045));
    // Repair13: opt-in A/B. Remote WebRTC tracks can deliver zero samples
    // long before the provider starts speaking. Buffering those zeros adds a
    // delay equal to that silence AFTER the private gate has been authorized.
    this.trimLeadingSilence = options?.processorOptions?.trimLeadingSilence === true;
    this.onsetThreshold = 0.00015; // only zero / near-digital-zero is discarded
    this.preroll = new Float32Array(Math.max(16, Math.round(rate * 0.008)));
    this.prerollCount = 0;
    this.prerollWrite = 0;
    this.signalDetected = false;
    this.bufferReadyReported = false;
    this.port.onmessage = (event) => {
      switch (event.data?.type) {
        case 'authorize': this.approved = true; break;
        case 'finish': this.finished = true; break;
        case 'abort':
          this.cancelled = true;
          this.approved = false;
          this.count = 0;
          this.port.postMessage({type:'aborted'});
          break;
        default: break;
      }
    };
  }
  process(inputs, outputs) {
    const output = outputs[0];
    if (!output || !output.length) return true;
    for (const channel of output) channel.fill(0);
    if (this.cancelled) return true;
    const input = inputs[0] || [];
    const a = input[0];
    const b = input[1] || a;
    const inputLength = a ? a.length : 0;
    // Capture mono mix as contiguous PCM. Neither trimmed nor untrimmed
    // samples reach the speaker before explicit authorization.
    const enqueue = (value) => {
      if (this.count === this.capacity) return false;
      this.ring[this.write] = value;
      this.write = (this.write + 1) % this.capacity;
      this.count++;
      return true;
    };
    for (let i = 0; i < inputLength && !this.finished; i++) {
      const sample = b ? (a[i] + b[i]) * 0.5 : a[i];
      if (!this.signalDetected && Math.abs(sample) > this.onsetThreshold) {
        this.signalDetected = true;
        this.port.postMessage({type:'first_pcm_signal'});
      }
      if (this.trimLeadingSilence && !this.signalDetected) {
        // Preserve just 8 ms of preceding signal so the first quiet phoneme
        // or attack isn't truncated; do not queue arbitrary idle silence.
        this.preroll[this.prerollWrite] = sample;
        this.prerollWrite = (this.prerollWrite + 1) % this.preroll.length;
        this.prerollCount = Math.min(this.prerollCount + 1, this.preroll.length);
        continue;
      }
      if (this.trimLeadingSilence && this.signalDetected && this.prerollCount) {
        const first = (this.prerollWrite - this.prerollCount + this.preroll.length) % this.preroll.length;
        for (let n = 0; n < this.prerollCount; n++) {
          if (!enqueue(this.preroll[(first + n) % this.preroll.length])) break;
        }
        this.prerollCount = 0;
      }
      if (!enqueue(sample)) {
        this.port.postMessage({type:'overflow'});
        this.cancelled = true;
        this.count = 0;
        return true; // Fail closed, never play overwritten samples.
      }
      if (this.signalDetected && !this.bufferReadyReported && this.count >= this.startBuffer) {
        this.bufferReadyReported = true;
        this.port.postMessage({type:'pcm_buffer_ready'});
      }
    }
    if (!this.approved) return true;
    if (!this.started) {
      if (this.count < this.startBuffer && !this.finished) return true;
      if (this.count === 0 && this.finished) {
        this.port.postMessage({type:'ended'});
        this.cancelled = true;
        return true;
      }
      this.started = true;
    }
    const length = output[0].length;
    let audible = false;
    for (let i = 0; i < length; i++) {
      if (!this.count) break;
      let value = this.ring[this.read];
      const tailRamp = this.finished ? Math.min(1, this.count / this.fadeSamples) : 1;
      this.read = (this.read + 1) % this.capacity;
      this.count--;
      // Tiny startup ramp avoids a discontinuity when authorization arrives mid-wave.
      const ramp = Math.min(1, (this.playedSamples + 1) / this.fadeSamples);
      value *= ramp * tailRamp;
      this.playedSamples++;
      for (const channel of output) channel[i] = value;
      if (Math.abs(value) > 0.0006) audible = true;
    }
    if (audible && !this.notifiedPlaying) {
      this.notifiedPlaying = true;
      this.port.postMessage({type:'playing'});
    }
    if (this.started && !this.finished && this.count === 0) {
      this.underflows++;
      // Sparse diagnostics only, so the worklet cannot flood the UI thread.
      if (this.underflows === 1 || this.underflows % 100 === 0) {
        this.port.postMessage({type:'underflow',count:this.underflows});
      }
    }
    if (this.finished && this.count === 0) {
      this.cancelled = true;
      this.port.postMessage({type:'ended'});
    }
    return true;
  }
}
registerProcessor('jarvis-pcm-gate', JarvisPcmGateProcessor);
