import { FormEvent, useEffect, useRef, useState } from 'react';

type JarvisState = 'connecting' | 'idle' | 'listening' | 'thinking' | 'speaking' | 'working' | 'error';

type RealtimeEvent = {
  type?: string;
  delta?: string;
  error?: { message?: string };
  response?: { status?: string; output?: Array<{ type?: string }> };
};

type Particle = {
  theta: number;
  phi: number;
  radius: number;
  size: number;
  speed: number;
  phase: number;
  hue: number;
  opacity: number;
  drift: number;
};

type LatencyMarks = {
  turn: number;
  speechStarted?: number;
  speechStopped?: number;
  responseCreated?: number;
  firstTranscript?: number;
  firstAudio?: number;
  reported?: boolean;
};

const stateLabels: Record<JarvisState, string> = {
  connecting: 'CONNECTING',
  idle: 'READY',
  listening: 'LISTENING',
  thinking: 'THINKING',
  speaking: 'SPEAKING',
  working: 'WORKING',
  error: 'OFFLINE',
};

function waitForIceGathering(pc: RTCPeerConnection): Promise<void> {
  if (pc.iceGatheringState === 'complete') return Promise.resolve();
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      cleanup();
      reject(new Error(`ICE gathering did not complete (${pc.iceGatheringState})`));
    }, 10_000);
    const onChange = () => {
      if (pc.iceGatheringState === 'complete') {
        cleanup();
        resolve();
      }
    };
    const cleanup = () => {
      window.clearTimeout(timer);
      pc.removeEventListener('icegatheringstatechange', onChange);
    };
    pc.addEventListener('icegatheringstatechange', onChange);
    onChange();
  });
}

function seededRandom(seed: number): () => number {
  let value = seed >>> 0;
  return () => {
    value = (value * 1664525 + 1013904223) >>> 0;
    return value / 0xffffffff;
  };
}

function createParticles(count: number): Particle[] {
  const random = seededRandom(0x4a415256);
  return Array.from({ length: count }, () => {
    const y = random() * 2 - 1;
    const shell = random() > 0.16;
    const shellRadius = 0.78 + Math.pow(random(), 0.22) * 0.22;
    const innerRadius = 0.24 + Math.pow(random(), 0.58) * 0.57;
    return {
      theta: random() * Math.PI * 2,
      phi: Math.acos(y),
      radius: shell ? shellRadius : innerRadius,
      size: shell ? 0.34 + random() * 0.92 : 0.28 + random() * 0.62,
      speed: 0.54 + random() * 0.92,
      phase: random() * Math.PI * 2,
      hue: random() * 72,
      opacity: 0.52 + random() * 0.48,
      drift: random() * 2 - 1,
    };
  });
}

function ParticleOrb({ state }: { state: JarvisState }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const stateRef = useRef(state);
  const particlesRef = useRef<Particle[]>(createParticles(1320));

  useEffect(() => { stateRef.current = state; }, [state]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext('2d');
    if (!context) return;

    type OrbMood = {
      speed: number;
      scale: number;
      brightness: number;
      hueShift: number;
      turbulence: number;
      radialMotion: number;
      coreEnergy: number;
      alpha: number;
    };

    const moods: Record<JarvisState, OrbMood> = {
      connecting: { speed: 0.34, scale: 0.985, brightness: 0.62, hueShift: -6, turbulence: 0.72, radialMotion: 0.003, coreEnergy: 0.56, alpha: 0.62 },
      idle:       { speed: 0.58, scale: 1.000, brightness: 1.00, hueShift: 0, turbulence: 1.00, radialMotion: 0.004, coreEnergy: 0.78, alpha: 1.00 },
      listening:  { speed: 0.78, scale: 1.018, brightness: 1.08, hueShift: -34, turbulence: 0.86, radialMotion: 0.016, coreEnergy: 0.98, alpha: 1.00 },
      thinking:   { speed: 1.42, scale: 0.995, brightness: 1.10, hueShift: 48, turbulence: 1.42, radialMotion: 0.006, coreEnergy: 1.06, alpha: 1.00 },
      speaking:   { speed: 0.92, scale: 1.002, brightness: 1.22, hueShift: -8, turbulence: 1.08, radialMotion: 0.005, coreEnergy: 1.24, alpha: 1.00 },
      working:    { speed: 1.68, scale: 0.992, brightness: 1.13, hueShift: -72, turbulence: 1.56, radialMotion: 0.009, coreEnergy: 1.13, alpha: 1.00 },
      error:      { speed: 0.26, scale: 0.985, brightness: 0.48, hueShift: 126, turbulence: 0.55, radialMotion: 0.002, coreEnergy: 0.46, alpha: 0.44 },
    };

    const blended: OrbMood = { ...moods.connecting };
    let frame = 0;
    let disposed = false;
    let previousTime = performance.now();
    const logicalSize = 420;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(logicalSize * dpr);
      canvas.height = Math.round(logicalSize * dpr);
      canvas.style.width = `${logicalSize}px`;
      canvas.style.height = `${logicalSize}px`;
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener('resize', resize);

    const draw = (time: number) => {
      if (disposed) return;
      const dt = Math.min(64, Math.max(1, time - previousTime));
      previousTime = time;
      const target = moods[stateRef.current];
      // One persistent particle field smoothly eases toward the next state instead of hard-swapping visuals.
      const blend = 1 - Math.exp(-dt / 420);
      (Object.keys(blended) as Array<keyof OrbMood>).forEach((key) => {
        blended[key] += (target[key] - blended[key]) * blend;
      });

      const current = stateRef.current;
      const center = logicalSize / 2;
      // Speaking should feel energized, not bouncy: less than half a percent scale motion.
      const speakingBreath = current === 'speaking' ? Math.sin(time * 0.0078) * 0.0036 : 0;
      const listeningBreath = current === 'listening' ? Math.sin(time * 0.0046) * 0.0055 : 0;
      const radius = 158 * (blended.scale + speakingBreath + listeningBreath);
      const t = time * 0.00015 * blended.speed;

      context.clearRect(0, 0, logicalSize, logicalSize);

      const aura = context.createRadialGradient(center, center, 16, center, center, 196);
      const auraHue = 222 + blended.hueShift;
      aura.addColorStop(0, `hsla(${auraHue}, 92%, 76%, ${0.10 * blended.coreEnergy * blended.alpha})`);
      aura.addColorStop(0.34, `hsla(${auraHue + 14}, 88%, 61%, ${0.052 * blended.brightness * blended.alpha})`);
      aura.addColorStop(0.64, `hsla(${auraHue + 48}, 82%, 58%, ${0.034 * blended.brightness * blended.alpha})`);
      aura.addColorStop(0.87, `hsla(${auraHue + 68}, 76%, 47%, ${0.014 * blended.alpha})`);
      aura.addColorStop(1, 'rgba(0,0,0,0)');
      context.fillStyle = aura;
      context.beginPath();
      context.arc(center, center, 198, 0, Math.PI * 2);
      context.fill();

      const projected = particlesRef.current.map((particle) => {
        const flowRate = blended.turbulence;
        const flowA = Math.sin(particle.theta * 2.7 + particle.phi * 1.8 + particle.phase + time * 0.00062 * flowRate);
        const flowB = Math.cos(particle.phi * 3.6 - particle.theta * 1.35 + particle.phase * 0.7 + time * 0.00048 * flowRate);
        const flowC = Math.sin((particle.theta + particle.phi) * 4.4 + time * 0.00034 * flowRate + particle.phase);
        const listeningFocus = current === 'listening'
          ? Math.sin(time * 0.0032 + particle.phase + particle.phi * 2.1) * blended.radialMotion
          : 0;
        const thinkingTwist = current === 'thinking'
          ? Math.sin(particle.phi * 2.4 + time * 0.0018) * 0.055 * blended.turbulence
          : 0;
        const workingStream = current === 'working'
          ? Math.cos(particle.theta * 1.8 - time * 0.0021 + particle.phase) * 0.034
          : 0;
        const phi = particle.phi + flowA * 0.050 * blended.turbulence + flowC * 0.018 + particle.drift * 0.012 + workingStream;
        const theta = particle.theta + t * particle.speed + flowB * 0.090 * blended.turbulence + flowA * 0.025 + thinkingTwist;
        const particleRadius = radius * particle.radius * (
          1 + flowC * 0.013 + Math.sin(time * 0.0005 + particle.phase) * 0.009 + listeningFocus
        );

        let x = Math.sin(phi) * Math.cos(theta);
        let y = Math.cos(phi);
        let z = Math.sin(phi) * Math.sin(theta);

        const tilt = -0.28;
        const yTilted = y * Math.cos(tilt) - z * Math.sin(tilt);
        const zTilted = y * Math.sin(tilt) + z * Math.cos(tilt);
        y = yTilted;
        z = zTilted;

        const perspective = 0.87 + (z + 1) * 0.09;
        return {
          x: center + x * particleRadius * perspective,
          y: center + y * particleRadius * perspective,
          z,
          size: particle.size * (0.66 + (z + 1) * 0.32),
          hue: 204 + particle.hue + blended.hueShift,
          opacity: particle.opacity,
        };
      }).sort((a, b) => a.z - b.z);

      context.globalCompositeOperation = 'lighter';
      for (const point of projected) {
        const depth = (point.z + 1) / 2;
        const alpha = (0.12 + depth * 0.74) * point.opacity * blended.alpha;
        const saturation = current === 'speaking' ? 90 : current === 'listening' ? 94 : 88;
        const lightness = Math.min(96, (62 + depth * 25) * blended.brightness);
        const glow = point.size > 0.9 || depth > 0.72;
        context.shadowBlur = glow ? (3 + depth * 5) * blended.coreEnergy : 0;
        context.shadowColor = `hsla(${point.hue}, ${saturation}%, ${lightness}%, ${alpha * 0.58})`;
        context.fillStyle = `hsla(${point.hue}, ${saturation}%, ${lightness}%, ${alpha})`;
        context.beginPath();
        context.arc(point.x, point.y, point.size, 0, Math.PI * 2);
        context.fill();
      }
      context.shadowBlur = 0;
      context.globalCompositeOperation = 'source-over';

      const coreSize = 25 + blended.coreEnergy * 5.2;
      const coreHue = 205 + blended.hueShift;
      const coreGlow = context.createRadialGradient(center, center, 0, center, center, 56);
      coreGlow.addColorStop(0, `hsla(${coreHue - 8}, 100%, 98%, ${0.92 * blended.alpha})`);
      coreGlow.addColorStop(0.13, `hsla(${coreHue}, 98%, 78%, ${0.66 * blended.coreEnergy * blended.alpha})`);
      coreGlow.addColorStop(0.39, `hsla(${coreHue + 14}, 92%, 63%, ${0.22 * blended.coreEnergy * blended.alpha})`);
      coreGlow.addColorStop(0.68, `hsla(${coreHue + 48}, 84%, 57%, ${0.066 * blended.coreEnergy * blended.alpha})`);
      coreGlow.addColorStop(1, 'rgba(31, 18, 77, 0)');
      context.fillStyle = coreGlow;
      context.beginPath();
      context.arc(center, center, coreSize + 27, 0, Math.PI * 2);
      context.fill();

      frame = window.requestAnimationFrame(draw);
    };

    frame = window.requestAnimationFrame(draw);
    return () => {
      disposed = true;
      window.cancelAnimationFrame(frame);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return (
    <div className={`avatar avatar--${state}`} aria-label={`Jarvis is ${state}`}>
      <canvas ref={canvasRef} className="avatar__canvas" width="420" height="420" />
      <div className="avatar__veil" />
    </div>
  );
}

function normalizeCaptionForDisplay(value: string): string {
  return value
    .replace(/[\r\n]+/g, ' ')
    .replace(/[ \t]+/g, ' ')
    .replace(/\s+([,.;:!?])/g, '$1')
    .replace(/([.!?])(?=[A-Z0-9])/g, '$1 ')
    .replace(/([,;:])(?=[A-Za-z0-9])/g, '$1 ');
}

function captionCharacterDelay(character: string, backlog: number): number {
  let delay = 54;
  if (character === ' ') delay = 20;
  else if (/[.!?…]/.test(character)) delay = 205;
  else if (/[,;:]/.test(character)) delay = 105;
  else if (/[—–]/.test(character)) delay = 115;
  else if (/['’"]/u.test(character)) delay = 38;

  if (backlog > 260) delay *= 0.70;
  else if (backlog > 180) delay *= 0.78;
  else if (backlog > 110) delay *= 0.86;
  else if (backlog > 60) delay *= 0.93;
  return Math.max(14, Math.round(delay));
}

export default function App() {
  const [jarvisState, setJarvisState] = useState<JarvisState>('connecting');
  const [caption, setCaption] = useState('');
  const [draft, setDraft] = useState('');
  const [detail, setDetail] = useState('Starting Jarvis…');
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const dcRef = useRef<RTCDataChannel | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const micRef = useRef<MediaStream | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const idleTimerRef = useRef<number | null>(null);
  const stoppingRef = useRef(false);
  const captionSourceRef = useRef('');
  const captionIndexRef = useRef(0);
  const captionTimerRef = useRef<number | null>(null);
  const captionResponseCompleteRef = useRef(false);
  const captionShouldIdleRef = useRef(false);
  const captionAudioStartedRef = useRef(false);
  const turnCounterRef = useRef(0);
  const latencyRef = useRef<LatencyMarks>({ turn: 0 });

  const setStateSafely = (next: JarvisState, message?: string) => {
    setJarvisState(next);
    if (message) setDetail(message);
  };

  const scheduleIdle = () => {
    if (idleTimerRef.current !== null) window.clearTimeout(idleTimerRef.current);
    idleTimerRef.current = window.setTimeout(() => {
      setJarvisState((current) => (current === 'speaking' || current === 'thinking' ? 'idle' : current));
    }, 850);
  };

  const sendControlMessage = (payload: object) => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(payload));
  };

  const forwardToCore = (event: RealtimeEvent) => {
    sendControlMessage({ kind: 'realtime_event', event });
  };

  const sendLatencySummary = () => {
    const marks = latencyRef.current;
    if (!marks.turn || !marks.speechStopped) return;
    const fromSpeechEnd = (value?: number) => value === undefined ? null : Math.round(value - marks.speechStopped!);
    sendControlMessage({
      kind: 'desktop_latency',
      turn: marks.turn,
      speech_end_to_response_created_ms: fromSpeechEnd(marks.responseCreated),
      speech_end_to_first_transcript_ms: fromSpeechEnd(marks.firstTranscript),
      speech_end_to_first_audio_ms: fromSpeechEnd(marks.firstAudio),
      response_created_to_first_audio_ms:
        marks.responseCreated !== undefined && marks.firstAudio !== undefined
          ? Math.round(marks.firstAudio - marks.responseCreated)
          : null,
    });
  };

  const clearCaptionPacing = (clearVisible: boolean) => {
    captionSourceRef.current = '';
    captionIndexRef.current = 0;
    captionResponseCompleteRef.current = false;
    captionShouldIdleRef.current = false;
    captionAudioStartedRef.current = false;
    if (captionTimerRef.current !== null) window.clearTimeout(captionTimerRef.current);
    captionTimerRef.current = null;
    if (clearVisible) setCaption('');
  };

  const pumpCaption = (initialDelay = 0) => {
    if (captionTimerRef.current !== null) return;

    const tick = () => {
      captionTimerRef.current = null;
      const source = captionSourceRef.current;
      const index = captionIndexRef.current;
      if (index >= source.length) {
        if (captionResponseCompleteRef.current && captionShouldIdleRef.current) {
          captionShouldIdleRef.current = false;
          scheduleIdle();
        }
        return;
      }

      const character = source[index];
      captionIndexRef.current = index + 1;
      setCaption(normalizeCaptionForDisplay(source.slice(0, captionIndexRef.current)));
      setStateSafely('speaking', 'Speaking');
      const backlog = source.length - captionIndexRef.current;
      captionTimerRef.current = window.setTimeout(tick, captionCharacterDelay(character, backlog));
    };

    captionTimerRef.current = window.setTimeout(tick, initialDelay);
  };

  const enqueueCaptionDelta = (delta: string) => {
    if (!delta) return;
    const cleaned = delta.replace(/[\r\n]+/g, ' ');
    const previous = captionSourceRef.current;
    const needsBoundarySpace = Boolean(
      previous
      && cleaned
      && !/\s$/.test(previous)
      && !/^\s/.test(cleaned)
      && /[.!?]/.test(previous.slice(-1))
      && /^[A-Z0-9]/.test(cleaned),
    );
    captionSourceRef.current = `${previous}${needsBoundarySpace ? ' ' : ''}${cleaned}`;
    if (captionAudioStartedRef.current) pumpCaption();
  };

  const handleRealtimeEvent = (event: RealtimeEvent) => {
    forwardToCore(event);
    const type = event.type || '';
    const now = performance.now();
    if (type === 'input_audio_buffer.speech_started') {
      turnCounterRef.current += 1;
      latencyRef.current = { turn: turnCounterRef.current, speechStarted: now };
      setStateSafely('listening', 'I’m listening');
    } else if (type === 'input_audio_buffer.speech_stopped') {
      latencyRef.current.speechStopped = now;
      setStateSafely('thinking', 'Thinking');
    } else if (type === 'response.created') {
      latencyRef.current.responseCreated ??= now;
      clearCaptionPacing(true);
      setStateSafely('thinking', 'Thinking');
    } else if (type === 'response.output_audio_transcript.delta') {
      latencyRef.current.firstTranscript ??= now;
      enqueueCaptionDelta(event.delta || '');
    } else if (type === 'output_audio_buffer.started') {
      latencyRef.current.firstAudio ??= now;
      captionAudioStartedRef.current = true;
      pumpCaption(45);
      setStateSafely('speaking', 'Speaking');
      if (!latencyRef.current.reported) {
        latencyRef.current.reported = true;
        sendLatencySummary();
      }
    } else if (type === 'response.function_call_arguments.done') {
      setStateSafely('working', 'Working');
    } else if (type === 'response.done') {
      const hasFunctionCall = Boolean(event.response?.output?.some((item) => item?.type === 'function_call'));
      if (hasFunctionCall) {
        clearCaptionPacing(false);
        setStateSafely('working', 'Working');
      } else if (event.response?.status === 'completed') {
        captionResponseCompleteRef.current = true;
        captionShouldIdleRef.current = true;
        if (!captionAudioStartedRef.current) {
          captionAudioStartedRef.current = true;
          pumpCaption(120);
        } else {
          pumpCaption();
        }
        if (!latencyRef.current.reported) {
          latencyRef.current.reported = true;
          sendLatencySummary();
        }
      } else if (event.response?.status === 'cancelled') {
        // Never reveal transcript that was generated but never actually spoken after barge-in.
        clearCaptionPacing(false);
      }
    } else if (type === 'error') {
      setStateSafely('error', event.error?.message || 'Realtime error');
    }
  };

  const stop = async () => {
    if (stoppingRef.current) return;
    stoppingRef.current = true;
    try {
      dcRef.current?.close();
      pcRef.current?.close();
      micRef.current?.getTracks().forEach((track) => track.stop());
      wsRef.current?.close();
      if (idleTimerRef.current !== null) window.clearTimeout(idleTimerRef.current);
      clearCaptionPacing(false);
      try { navigator.sendBeacon('/api/realtime/end'); } catch (_) { /* best effort */ }
    } finally {
      dcRef.current = null;
      pcRef.current = null;
      micRef.current = null;
      wsRef.current = null;
    }
  };

  const start = async () => {
    try {
      setStateSafely('connecting', 'Starting Jarvis…');
      const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
      const ws = new WebSocket(`${scheme}://${location.host}/ws/control`);
      wsRef.current = ws;
      await new Promise<void>((resolve, reject) => {
        ws.onopen = () => resolve();
        ws.onerror = () => reject(new Error('Could not connect to Jarvis Core'));
      });
      ws.onmessage = (message) => {
        let payload: any;
        try { payload = JSON.parse(message.data); } catch { return; }
        if (payload.kind === 'realtime_send' && dcRef.current?.readyState === 'open') {
          dcRef.current.send(JSON.stringify(payload.event));
        } else if (payload.kind === 'lab_command' && payload.command === 'close') {
          void stop();
        }
      };
      ws.onclose = () => {
        if (!stoppingRef.current) setStateSafely('error', 'Jarvis Core disconnected');
      };

      const mic = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      micRef.current = mic;

      const pc = new RTCPeerConnection();
      pcRef.current = pc;
      mic.getTracks().forEach((track) => pc.addTrack(track, mic));
      pc.ontrack = async (event) => {
        const remote = event.streams[0] || new MediaStream([event.track]);
        if (audioRef.current) {
          audioRef.current.srcObject = remote;
          try { await audioRef.current.play(); } catch (_) { /* autoplay is enabled by Electron */ }
        }
      };
      pc.onconnectionstatechange = () => {
        if (pc.connectionState === 'connected') setStateSafely('idle', 'Ready');
        if (['failed', 'disconnected', 'closed'].includes(pc.connectionState) && !stoppingRef.current) {
          setStateSafely('error', `WebRTC ${pc.connectionState}`);
        }
      };

      const dc = pc.createDataChannel('oai-events');
      dcRef.current = dc;
      dc.onmessage = (message) => {
        try { handleRealtimeEvent(JSON.parse(message.data)); } catch (_) { /* ignore malformed provider event */ }
      };
      dc.onopen = () => setStateSafely('idle', 'Ready');

      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      await waitForIceGathering(pc);
      const response = await fetch('/api/realtime/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sdp: pc.localDescription?.sdp || '' }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || `Realtime session failed (${response.status})`);
      await pc.setRemoteDescription({ type: 'answer', sdp: body.sdp });
      setStateSafely('idle', 'Ready');
    } catch (error) {
      setStateSafely('error', error instanceof Error ? error.message : String(error));
    }
  };

  useEffect(() => {
    stoppingRef.current = false;
    void start();
    const unload = () => { void stop(); };
    window.addEventListener('beforeunload', unload);
    return () => {
      window.removeEventListener('beforeunload', unload);
      void stop();
    };
    // The desktop alpha intentionally owns exactly one session per renderer lifetime.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submitText = (event: FormEvent) => {
    event.preventDefault();
    const text = draft.trim();
    const dc = dcRef.current;
    if (!text || !dc || dc.readyState !== 'open') return;

    if (jarvisState === 'speaking') dc.send(JSON.stringify({ type: 'response.cancel' }));
    turnCounterRef.current += 1;
    const now = performance.now();
    latencyRef.current = { turn: turnCounterRef.current, speechStarted: now, speechStopped: now };
    setDraft('');
    clearCaptionPacing(true);
    setStateSafely('thinking', 'Thinking');
    dc.send(JSON.stringify({
      type: 'conversation.item.create',
      item: {
        type: 'message',
        role: 'user',
        content: [{ type: 'input_text', text }],
      },
    }));
    dc.send(JSON.stringify({ type: 'response.create' }));
  };

  return (
    <main className="shell">
      <section className="jarvis" aria-live="polite">
        <header className="brand">
          <span className={`brand__dot brand__dot--${jarvisState}`} />
          <span>JARVIS</span>
        </header>

        <ParticleOrb state={jarvisState} />

        <div className="state-label">{stateLabels[jarvisState]}</div>
        <div className={`caption ${caption ? 'caption--active' : ''}`}>
          {caption || (jarvisState === 'error' ? detail : '\u00A0')}
        </div>

        <form className="composer" onSubmit={submitText}>
          <input
            aria-label="Type to Jarvis"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={jarvisState === 'error' ? 'Jarvis is offline' : 'Ask Jarvis…'}
            disabled={jarvisState === 'connecting' || jarvisState === 'error'}
            autoComplete="off"
          />
          <button type="submit" disabled={!draft.trim() || jarvisState === 'connecting' || jarvisState === 'error'} aria-label="Send">
            <span>↗</span>
          </button>
        </form>

        <p className="hint">Speak naturally, or type instead.</p>
        <audio ref={audioRef} autoPlay />
      </section>
    </main>
  );
}
