/**
 * Experimental sample-continuous, private Realtime audio gate. One incoming
 * WebRTC track is routed to a sample buffer in an AudioWorklet. Until the
 * independent text-only tool decision authorizes it, the worklet outputs
 * *only zeros*. This is not sentence chunking or separate synthesis.
 *
 * The HTML media element for the provider track stays muted; cancellation
 * invalidates this object and silences the worklet before freeing resources.
 */
export class StreamingPcmGate {
  private context: AudioContext | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private gate: AudioWorkletNode | null = null;
  private disposed = false;
  private approved = false;
  private finished = false;
  private startedPlayback = false;
  private timer: ReturnType<typeof setTimeout> | null = null;
  readonly startedAt = performance.now();
  private constructor(private readonly played: () => void, private readonly ended: () => void,
    private readonly fail: (reason: string) => void,
    private readonly underflow: (count: number) => void) {}

  static supported(): boolean {
    return typeof AudioContext !== 'undefined' &&
      typeof AudioWorkletNode !== 'undefined' &&
      typeof MediaStream !== 'undefined';
  }

  static async create(stream: MediaStream, played: () => void, ended: () => void,
    fail: (reason: string) => void, underflow: (count: number) => void): Promise<StreamingPcmGate> {
    if (!StreamingPcmGate.supported()) throw new Error('AudioWorklet PCM playback unsupported');
    const self = new StreamingPcmGate(played, ended, fail, underflow);
    try {
      // Never connect the remote audio element directly to speaker output.
      const context = new AudioContext({latencyHint:'interactive'});
      self.context = context;
      await context.audioWorklet.addModule(new URL('./pcmGateProcessor.js', import.meta.url).href);
      if (self.disposed) return self;
      self.source = context.createMediaStreamSource(stream);
      self.gate = new AudioWorkletNode(context, 'jarvis-pcm-gate', {
        numberOfInputs:1, numberOfOutputs:1, outputChannelCount:[2],
        processorOptions:{rate:context.sampleRate},
      });
      self.gate.port.onmessage = (event: MessageEvent) => {
        if (self.disposed) return;
        if (event.data?.type === 'playing' && self.approved && !self.startedPlayback) {
          self.startedPlayback = true;
          self.played();
        } else if (event.data?.type === 'ended') {
          self.ended();
        } else if (event.data?.type === 'underflow') {
          self.underflow(Number(event.data.count || 0));
        } else if (event.data?.type === 'overflow') {
          self.abort('private_pcm_overflow');
        }
      };
      // Input is only made audible through the worklet once authorized.
      self.source.connect(self.gate);
      self.gate.connect(context.destination);
      await context.resume();
      if (self.approved) self.gate.port.postMessage({type:'authorize'});
      if (self.finished) self.gate.port.postMessage({type:'finish'});
      return self;
    } catch (error) {
      self.abort();
      throw error;
    }
  }

  authorize(): void {
    if (this.disposed || this.approved) return;
    this.approved = true;
    this.gate?.port.postMessage({type:'authorize'});
  }
  finish(): void {
    if (this.disposed || this.finished) return;
    this.finished = true;
    this.gate?.port.postMessage({type:'finish'});
    // Fail closed if stream never drains; no indefinite listening/output session.
    this.timer = setTimeout(() => this.abort('pcm_drain_timeout'), 30000);
  }
  abort(reason = 'cancelled'): void {
    if (this.disposed) return;
    this.disposed = true;
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
    this.gate?.port.postMessage({type:'abort'});
    try { this.source?.disconnect(); } catch (_) { /* best effort */ }
    try { this.gate?.disconnect(); } catch (_) { /* best effort */ }
    this.source = null;
    this.gate = null;
    const context = this.context;
    this.context = null;
    if (context) void context.close().catch(() => { /* best effort */ });
    if (reason !== 'cancelled') this.fail(reason);
  }
}
