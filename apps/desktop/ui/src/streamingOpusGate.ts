/** Experimental private continuous-audio buffer. Never connects the provider track to speakers. */
export class StreamingOpusGate {
  private recorder: MediaRecorder | null = null;
  private source: MediaSource | null = null;
  private buffer: SourceBuffer | null = null;
  private player: HTMLAudioElement | null = null;
  private url = '';
  private waiting: Uint8Array[] = [];
  private chain: Promise<void> = Promise.resolve();
  private approved = false;
  private finished = false;
  private disposed = false;
  private bytes = 0;
  private playbackRequested = false;
  readonly startedAt = performance.now();
  static supported(): boolean {
    return typeof MediaRecorder !== 'undefined' && typeof MediaSource !== 'undefined' &&
      MediaRecorder.isTypeSupported('audio/webm;codecs=opus') &&
      MediaSource.isTypeSupported('audio/webm;codecs=opus');
  }
  constructor(stream: MediaStream, private readonly played: () => void,
    private readonly ended: () => void, private readonly fail: (reason: string) => void) {
    if (!StreamingOpusGate.supported()) throw new Error('Opus MediaRecorder/MediaSource streaming unsupported');
    this.recorder = new MediaRecorder(stream, {mimeType:'audio/webm;codecs=opus'});
    this.recorder.ondataavailable = (evt: BlobEvent) => {
      if (!evt.data.size || this.disposed) return;
      this.chain = this.chain.then(async () => {
        const bytes = new Uint8Array(await evt.data.arrayBuffer());
        if (this.disposed) return;
        this.bytes += bytes.byteLength;
        if (this.bytes > 8_000_000) { this.abort('private_audio_cap'); return; }
        this.waiting.push(bytes);
        this.pump();
      }).catch(() => this.abort('chunk_decode_error'));
    };
    this.recorder.onstop = () => { this.finished = true; void this.chain.then(() => this.pump()); };
    this.recorder.start(100);
  }
  get bytesHeld(): number { return this.bytes; }
  authorize(): void {
    if (this.disposed || this.approved) return;
    this.approved = true;
    this.source = new MediaSource();
    this.url = URL.createObjectURL(this.source);
    this.player = new Audio(this.url);
    this.player.onplaying = () => { if (!this.disposed) this.played(); };
    this.player.onended = () => { if (!this.disposed) this.ended(); };
    this.source.addEventListener('sourceopen', () => {
      if (this.disposed || !this.source) return;
      try {
        this.buffer = this.source.addSourceBuffer('audio/webm;codecs=opus');
        this.buffer.mode = 'sequence';
        this.buffer.addEventListener('updateend', () => this.pump());
        this.pump();
      } catch (_) { this.abort('media_source_init_failed'); }
    }, {once:true});
  }
  private pump(): void {
    if (this.disposed || !this.approved || !this.buffer || !this.source) return;
    if (this.buffer.updating || this.source.readyState !== 'open') return;
    if (this.waiting.length) {
      try {
        this.buffer.appendBuffer(this.waiting.shift()!);
        if (!this.playbackRequested) {
          this.playbackRequested = true;
          void this.player?.play().catch(() => this.abort('audio_playback_failed'));
        }
      } catch (_) { this.abort('media_source_append_failed'); }
    } else if (this.finished) {
      try { this.source.endOfStream(); } catch (_) { /* best effort */ }
    }
  }
  finish(): void {
    if (!this.recorder || this.recorder.state === 'inactive') return;
    try { this.recorder.stop(); } catch (_) { this.abort('recorder_stop_failed'); }
  }
  abort(reason = 'cancelled'): void {
    if (this.disposed) return;
    const report = reason !== 'cancelled';
    this.disposed = true;
    if (this.recorder) {
      this.recorder.ondataavailable = null;
      this.recorder.onstop = null;
      if (this.recorder.state !== 'inactive') try { this.recorder.stop(); } catch (_) { /* cleanup */ }
    }
    this.recorder = null;
    if (this.player) {
      this.player.pause();
      this.player.removeAttribute('src');
      this.player.load();
    }
    this.player = null;
    if (this.url) URL.revokeObjectURL(this.url);
    this.url = '';
    this.waiting = [];
    if (report) this.fail(reason);
  }
}
