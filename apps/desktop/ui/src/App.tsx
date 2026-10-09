import { FormEvent, useEffect, useRef, useState } from 'react';

type PresenceState = 'sleeping' | 'awake';
type JarvisState = 'sleeping' | 'waking' | 'connecting' | 'idle' | 'listening' | 'thinking' | 'speaking' | 'working' | 'error';

type RealtimeContent = {
  type?: string;
  transcript?: string;
  text?: string;
};

type RealtimeItem = {
  id?: string;
  type?: string;
  name?: string;
  role?: string;
  content?: RealtimeContent[];
};

type RealtimeEvent = {
  type?: string;
  delta?: string;
  transcript?: string;
  response_id?: string;
  item_id?: string;
  name?: string;
  arguments?: string;
  call_id?: string;
  item?: RealtimeItem;
  error?: { message?: string };
  response?: { id?: string; status?: string; output?: RealtimeItem[] };
};

type ResponsePolicy = {
  max_output_tokens?: number | 'inf';
  instructions?: string;
  output_modalities?: string[];
  tools?: unknown[];
  tool_choice?: string | { type: 'function'; name: string };
  reasoning?: { effort?: string };
  metadata?: Record<string, string>;
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
  routeDecided?: number;
  route?: string;
  firstTranscript?: number;
  firstAudio?: number;
  reported?: boolean;
};

const stateLabels: Record<JarvisState, string> = {
  sleeping: 'SLEEPING',
  waking: 'WAKING',
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
      sleeping:   { speed: 0.16, scale: 0.968, brightness: 0.44, hueShift: 56, turbulence: 0.44, radialMotion: 0.001, coreEnergy: 0.34, alpha: 0.48 },
      waking:     { speed: 0.92, scale: 1.018, brightness: 1.12, hueShift: 14, turbulence: 1.24, radialMotion: 0.018, coreEnergy: 1.08, alpha: 0.96 },
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
    // Keep one 420-unit drawing coordinate system while CSS scales the visible orb with the viewport.
    const logicalSize = 420;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const cssSize = Math.max(1, canvas.getBoundingClientRect().width || logicalSize);
      canvas.width = Math.round(cssSize * dpr);
      canvas.height = Math.round(cssSize * dpr);
      const visualScale = cssSize / logicalSize;
      context.setTransform(dpr * visualScale, 0, 0, dpr * visualScale, 0, 0);
    };
    resize();
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(canvas);
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
      resizeObserver.disconnect();
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

function responseTranscript(response: RealtimeEvent['response']): string {
  if (!response?.output) return '';
  const pieces: string[] = [];
  for (const item of response.output) {
    if (item.type !== 'message' || !Array.isArray(item.content)) continue;
    for (const content of item.content) {
      const value = String(content.transcript || content.text || '').trim();
      if (value) pieces.push(value);
    }
  }
  return normalizeCaptionForDisplay(pieces.join(' ')).trim();
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


function downsampleTo16k(input: Float32Array, sourceRate: number): Int16Array {
  if (!Number.isFinite(sourceRate) || sourceRate < 16_000) {
    throw new Error(`Unsupported microphone sample rate: ${sourceRate}`);
  }
  const ratio = sourceRate / 16_000;
  const outputLength = Math.max(1, Math.floor(input.length / ratio));
  const output = new Int16Array(outputLength);
  for (let i = 0; i < outputLength; i += 1) {
    const start = Math.floor(i * ratio);
    const end = Math.max(start + 1, Math.min(input.length, Math.floor((i + 1) * ratio)));
    let sum = 0;
    for (let j = start; j < end; j += 1) sum += input[j];
    const sample = Math.max(-1, Math.min(1, sum / Math.max(1, end - start)));
    output[i] = sample < 0 ? Math.round(sample * 32768) : Math.round(sample * 32767);
  }
  return output;
}

function appendInt16(left: Int16Array, right: Int16Array): Int16Array {
  if (!left.length) return right.slice();
  const combined = new Int16Array(left.length + right.length);
  combined.set(left, 0);
  combined.set(right, left.length);
  return combined;
}

export default function App() {
  const [presence, setPresence] = useState<PresenceState>('sleeping');
  const [jarvisState, setJarvisState] = useState<JarvisState>('sleeping');
  const [caption, setCaption] = useState('');
  const [draft, setDraft] = useState('');
  const [detail, setDetail] = useState('Preparing local wake listener…');
  const [transcriptExpanded, setTranscriptExpanded] = useState(false);
  const [captionOverflow, setCaptionOverflow] = useState(false);
  const [captionBrowsing, setCaptionBrowsing] = useState(false);

  const presenceRef = useRef<PresenceState>('sleeping');
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const dcRef = useRef<RTCDataChannel | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const wakeWsRef = useRef<WebSocket | null>(null);
  const micRef = useRef<MediaStream | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const captionViewportRef = useRef<HTMLDivElement | null>(null);
  const captionStickToLatestRef = useRef(true);
  const wakeAudioContextRef = useRef<AudioContext | null>(null);
  const wakeProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const wakeSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const wakeGainRef = useRef<GainNode | null>(null);
  const wakePendingRef = useRef<Int16Array>(new Int16Array(0));
  const idleTimerRef = useRef<number | null>(null);
  const idleSleepSecondsRef = useRef(60);
  const wakePhraseRef = useRef('Jarvis');
  const stoppingRef = useRef(false);
  const realtimeClosingRef = useRef(false);
  const wakeClosingRef = useRef(false);
  const captionSourceRef = useRef('');
  const captionIndexRef = useRef(0);
  const captionTimerRef = useRef<number | null>(null);
  const captionResponseCompleteRef = useRef(false);
  const captionShouldIdleRef = useRef(false);
  const captionAudioStartedRef = useRef(false);
  const audioPlayingRef = useRef(false);
  const turnCounterRef = useRef(0);
  const responsePolicyRef = useRef<ResponsePolicy | null>(null);
  const activeResponseIdRef = useRef('');
  const suppressedResponseIdsRef = useRef<Set<string>>(new Set());
  const responseMessageItemIdsRef = useRef<Map<string, Set<string>>>(new Map());
  const userItemTurnsRef = useRef<Map<string, number>>(new Map());
  const conversationTraceRef = useRef(true);
  const latencyRef = useRef<LatencyMarks>({ turn: 0 });

  const setStateSafely = (next: JarvisState, message?: string) => {
    setJarvisState(next);
    if (message) setDetail(message);
  };

  const setPresenceSafely = (next: PresenceState) => {
    presenceRef.current = next;
    setPresence(next);
  };

  const clearIdleTimer = () => {
    if (idleTimerRef.current !== null) window.clearTimeout(idleTimerRef.current);
    idleTimerRef.current = null;
  };

  const scheduleIdle = (delayMs = 220) => {
    window.setTimeout(() => {
      if (presenceRef.current !== 'awake') return;
      setJarvisState((current) => (current === 'speaking' || current === 'thinking' ? 'idle' : current));
    }, delayMs);
  };

  const sendControlMessage = (payload: object) => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(payload));
  };

  const forwardToCore = (event: RealtimeEvent) => {
    sendControlMessage({ kind: 'realtime_event', event });
  };

  const responseIdForEvent = (event: RealtimeEvent): string => {
    return String(event.response_id || event.response?.id || activeResponseIdRef.current || '').trim();
  };

  const responseIsSuppressed = (event: RealtimeEvent): boolean => {
    const responseId = responseIdForEvent(event);
    return Boolean(responseId && suppressedResponseIdsRef.current.has(responseId));
  };

  const rememberResponseItem = (event: RealtimeEvent) => {
    if (event.type !== 'response.output_item.added') return;
    const responseId = responseIdForEvent(event);
    const itemId = String(event.item?.id || event.item_id || '').trim();
    if (!responseId || !itemId || event.item?.type !== 'message') return;
    const ids = responseMessageItemIdsRef.current.get(responseId) || new Set<string>();
    ids.add(itemId);
    responseMessageItemIdsRef.current.set(responseId, ids);
  };

  const trimSuppressedResponses = () => {
    while (suppressedResponseIdsRef.current.size > 64) {
      const oldest = suppressedResponseIdsRef.current.values().next().value;
      if (!oldest) break;
      suppressedResponseIdsRef.current.delete(oldest);
      responseMessageItemIdsRef.current.delete(oldest);
    }
  };

  const suppressDelegationPreamble = (event: RealtimeEvent) => {
    const responseId = responseIdForEvent(event);
    if (responseId) {
      suppressedResponseIdsRef.current.add(responseId);
      trimSuppressedResponses();
    }

    // A delegation response is internal control traffic, not user-facing speech.
    // If the provider generated a pre-tool sentence anyway, mute and purge it before
    // buffered WebRTC audio or transcript pacing can leak internal routing narration.
    if (audioRef.current) audioRef.current.muted = true;
    audioPlayingRef.current = false;
    clearCaptionPacing(true);

    const dc = dcRef.current;
    if (dc?.readyState === 'open') {
      try { dc.send(JSON.stringify({ type: 'output_audio_buffer.clear' })); } catch (_) { /* best effort */ }
    }
    setStateSafely('working', 'Working');
  };

  const suppressTurnRouterOutput = (event: RealtimeEvent) => {
    const responseId = responseIdForEvent(event);
    if (responseId) {
      suppressedResponseIdsRef.current.add(responseId);
      trimSuppressedResponses();
    }

    // Repair3 makes the routing response text-only at response.create, so there
    // should be no audio to hear. Keep a client-side mute/clear as defense in
    // depth if a provider ever violates that response-level modality contract.
    if (audioRef.current) audioRef.current.muted = true;
    audioPlayingRef.current = false;
    clearCaptionPacing(true);
    const dc = dcRef.current;
    if (dc?.readyState === 'open') {
      try { dc.send(JSON.stringify({ type: 'output_audio_buffer.clear' })); } catch (_) { /* best effort */ }
    }
    setStateSafely('thinking', 'Thinking');
  };

  const deleteSuppressedResponseMessages = (event: RealtimeEvent) => {
    const responseId = responseIdForEvent(event);
    if (!responseId) return;
    const itemIds = responseMessageItemIdsRef.current.get(responseId);
    if (!itemIds?.size) return;
    const dc = dcRef.current;
    if (dc?.readyState === 'open') {
      for (const itemId of itemIds) {
        try {
          dc.send(JSON.stringify({ type: 'conversation.item.delete', item_id: itemId }));
        } catch (_) { /* best effort */ }
      }
    }
    responseMessageItemIdsRef.current.delete(responseId);
  };

  const sendLatencySummary = () => {
    const marks = latencyRef.current;
    if (!marks.turn || !marks.speechStopped) return;
    const fromSpeechEnd = (value?: number) => value === undefined ? null : Math.round(value - marks.speechStopped!);
    sendControlMessage({
      kind: 'desktop_latency',
      turn: marks.turn,
      route: marks.route || null,
      speech_end_to_route_ms: fromSpeechEnd(marks.routeDecided),
      route_to_first_audio_ms:
        marks.routeDecided !== undefined && marks.firstAudio !== undefined
          ? Math.round(marks.firstAudio - marks.routeDecided)
          : null,
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
    if (clearVisible) {
      captionStickToLatestRef.current = true;
      setCaptionBrowsing(false);
      setCaptionOverflow(false);
      setCaption('');
    }
  };

  const pumpCaption = (initialDelay = 0) => {
    if (captionTimerRef.current !== null) return;
    const tick = () => {
      captionTimerRef.current = null;
      const source = captionSourceRef.current;
      const index = captionIndexRef.current;
      if (index >= source.length) {
        // The transcript can finish before Cedar's buffered WebRTC audio; captions never end the speaking state.
        return;
      }
      const character = source[index];
      captionIndexRef.current = index + 1;
      setCaption(normalizeCaptionForDisplay(source.slice(0, captionIndexRef.current)));
      const backlog = source.length - captionIndexRef.current;
      captionTimerRef.current = window.setTimeout(tick, captionCharacterDelay(character, backlog));
    };
    captionTimerRef.current = window.setTimeout(tick, initialDelay);
  };

  const finalizeCaptionPacing = () => {
    if (captionTimerRef.current !== null) window.clearTimeout(captionTimerRef.current);
    captionTimerRef.current = null;
    captionIndexRef.current = captionSourceRef.current.length;
    if (captionSourceRef.current) {
      setCaption(normalizeCaptionForDisplay(captionSourceRef.current));
    }
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

  const armIdleSleep = () => {
    clearIdleTimer();
    if (presenceRef.current !== 'awake') return;
    idleTimerRef.current = window.setTimeout(() => {
      void enterSleep('idle_timeout');
    }, Math.max(1, idleSleepSecondsRef.current) * 1000);
  };

  const noteActivity = () => {
    if (presenceRef.current === 'awake') armIdleSleep();
  };

  const ensureMic = async (): Promise<MediaStream> => {
    if (micRef.current && micRef.current.getAudioTracks().some((track) => track.readyState === 'live')) {
      return micRef.current;
    }
    const mic = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    micRef.current = mic;
    return mic;
  };

  const stopWakeAudioTap = async () => {
    const processor = wakeProcessorRef.current;
    const source = wakeSourceRef.current;
    const gain = wakeGainRef.current;
    wakeProcessorRef.current = null;
    wakeSourceRef.current = null;
    wakeGainRef.current = null;
    wakePendingRef.current = new Int16Array(0);
    try { processor?.disconnect(); } catch (_) { /* best effort */ }
    try { source?.disconnect(); } catch (_) { /* best effort */ }
    try { gain?.disconnect(); } catch (_) { /* best effort */ }
    const context = wakeAudioContextRef.current;
    wakeAudioContextRef.current = null;
    if (context && context.state !== 'closed') {
      try { await context.close(); } catch (_) { /* best effort */ }
    }
  };

  const stopWakeListening = async () => {
    wakeClosingRef.current = true;
    await stopWakeAudioTap();
    try { wakeWsRef.current?.close(); } catch (_) { /* best effort */ }
    wakeWsRef.current = null;
    wakeClosingRef.current = false;
  };

  const startWakeAudioTap = async (ws: WebSocket) => {
    const mic = await ensureMic();
    if (wakeAudioContextRef.current) return;
    const context = new AudioContext();
    wakeAudioContextRef.current = context;
    if (context.state === 'suspended') await context.resume();
    const source = context.createMediaStreamSource(mic);
    const processor = context.createScriptProcessor(4096, 1, 1);
    const gain = context.createGain();
    gain.gain.value = 0;
    wakeSourceRef.current = source;
    wakeProcessorRef.current = processor;
    wakeGainRef.current = gain;
    processor.onaudioprocess = (event) => {
      if (ws.readyState !== WebSocket.OPEN || presenceRef.current !== 'sleeping') return;
      const samples = event.inputBuffer.getChannelData(0);
      let downsampled: Int16Array;
      try { downsampled = downsampleTo16k(samples, context.sampleRate); } catch { return; }
      let pending = appendInt16(wakePendingRef.current, downsampled);
      const frameSamples = 480; // 30 ms at 16 kHz; matches LocalWakeListener.
      while (pending.length >= frameSamples && ws.readyState === WebSocket.OPEN) {
        const frame = pending.slice(0, frameSamples);
        ws.send(frame.buffer);
        pending = pending.slice(frameSamples);
      }
      wakePendingRef.current = pending;
    };
    source.connect(processor);
    processor.connect(gain);
    gain.connect(context.destination);
  };

  const startWakeListening = async () => {
    if (stoppingRef.current || presenceRef.current !== 'sleeping') return;
    await stopWakeListening();
    setStateSafely('sleeping', `Say “${wakePhraseRef.current}” when you need me.`);
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${scheme}://${location.host}/ws/wake`);
    wakeWsRef.current = ws;
    ws.binaryType = 'arraybuffer';
    ws.onmessage = (message) => {
      let payload: any;
      try { payload = JSON.parse(message.data); } catch { return; }
      if (payload.kind === 'wake_preparing') {
        setStateSafely('sleeping', 'Preparing local wake listener…');
      } else if (payload.kind === 'wake_ready') {
        const phrases = Array.isArray(payload.wake_phrases) ? payload.wake_phrases : [];
        if (phrases.length) wakePhraseRef.current = String(phrases[phrases.length - 1] || 'Jarvis');
        if (Number(payload.idle_sleep_seconds) > 0) idleSleepSecondsRef.current = Number(payload.idle_sleep_seconds);
        setStateSafely('sleeping', `Say “${wakePhraseRef.current}” when you need me.`);
        void startWakeAudioTap(ws);
      } else if (payload.kind === 'wake_detected') {
        const command = String(payload.command_text || '').trim();
        void startRealtimeSession(command, 'local_wake_phrase');
      } else if (payload.kind === 'wake_unavailable') {
        setStateSafely('sleeping', 'Voice wake is unavailable; type a message to wake Jarvis.');
      }
    };
    ws.onclose = () => {
      if (!wakeClosingRef.current && presenceRef.current === 'sleeping' && !stoppingRef.current) {
        window.setTimeout(() => { void startWakeListening(); }, 650);
      }
    };
  };

  const silenceRealtimeOutput = () => {
    const dc = dcRef.current;
    if (dc?.readyState === 'open') {
      try { dc.send(JSON.stringify({ type: 'response.cancel' })); } catch (_) { /* best effort */ }
      try { dc.send(JSON.stringify({ type: 'output_audio_buffer.clear' })); } catch (_) { /* best effort */ }
      try { dc.send(JSON.stringify({ type: 'input_audio_buffer.clear' })); } catch (_) { /* best effort */ }
    }
    audioPlayingRef.current = false;
    if (audioRef.current) {
      try { audioRef.current.pause(); } catch (_) { /* best effort */ }
      audioRef.current.muted = true;
      audioRef.current.srcObject = null;
    }
  };

  const stopRealtimeSession = async ({ notifyServer = true }: { notifyServer?: boolean } = {}) => {
    realtimeClosingRef.current = true;
    clearIdleTimer();
    silenceRealtimeOutput();
    dcRef.current?.close();
    pcRef.current?.close();
    wsRef.current?.close();
    dcRef.current = null;
    pcRef.current = null;
    wsRef.current = null;
    activeResponseIdRef.current = '';
    suppressedResponseIdsRef.current.clear();
    responseMessageItemIdsRef.current.clear();
    if (notifyServer) {
      try { await fetch('/api/realtime/end', { method: 'POST' }); } catch (_) { /* best effort */ }
    }
    realtimeClosingRef.current = false;
  };

  const enterSleep = async (reason: string) => {
    if (presenceRef.current === 'sleeping' || stoppingRef.current) return;
    setPresenceSafely('sleeping');
    clearIdleTimer();
    setStateSafely('sleeping', reason === 'idle_timeout' ? 'Sleeping after 60 seconds of inactivity.' : `Say “${wakePhraseRef.current}” when you need me.`);
    clearCaptionPacing(true);
    setTranscriptExpanded(false);
    silenceRealtimeOutput();
    await stopRealtimeSession({ notifyServer: false });
    try {
      await fetch('/api/presence/sleep', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason }),
      });
    } catch (_) { /* best effort */ }
    if (!stoppingRef.current) await startWakeListening();
  };

  const requestNormalRealtimeResponse = (dc: RTCDataChannel | null = dcRef.current) => {
    if (!dc || dc.readyState !== 'open') return false;
    const event: Record<string, unknown> = { type: 'response.create' };
    if (responsePolicyRef.current) {
      event.response = {
        ...responsePolicyRef.current,
        metadata: {
          ...(responsePolicyRef.current.metadata || {}),
          jarvis_turn: String(latencyRef.current.turn || turnCounterRef.current || 0),
        },
      };
    }
    dc.send(JSON.stringify(event));
    return true;
  };

  const dispatchTextToRealtime = (text: string, source = 'typed') => {
    const dc = dcRef.current;
    const clean = text.trim();
    if (!clean || !dc || dc.readyState !== 'open') return false;
    turnCounterRef.current += 1;
    const now = performance.now();
    latencyRef.current = { turn: turnCounterRef.current, speechStarted: now, speechStopped: now };
    if (conversationTraceRef.current) {
      sendControlMessage({
        kind: 'desktop_user',
        turn: turnCounterRef.current,
        source,
        text: clean,
      });
    }
    clearCaptionPacing(true);
    setStateSafely('thinking', 'Thinking');
    dc.send(JSON.stringify({
      type: 'conversation.item.create',
      item: { type: 'message', role: 'user', content: [{ type: 'input_text', text: clean }] },
    }));
    requestNormalRealtimeResponse(dc);
    noteActivity();
    return true;
  };

  const handleRealtimeEvent = (event: RealtimeEvent) => {
    const type = event.type || '';
    const now = performance.now();
    if (
      (type === 'conversation.item.created' || type === 'conversation.item.added' || type === 'conversation.item.done')
      && event.item?.role === 'user'
      && event.item?.id
    ) {
      const itemId = String(event.item.id);
      if (!userItemTurnsRef.current.has(itemId)) {
        userItemTurnsRef.current.set(itemId, latencyRef.current.turn || turnCounterRef.current || 0);
        while (userItemTurnsRef.current.size > 64) {
          userItemTurnsRef.current.delete(userItemTurnsRef.current.keys().next().value || '');
        }
      }
    }
    if (type === 'conversation.item.input_audio_transcription.completed') {
      const itemId = String(event.item_id || '');
      const turn = userItemTurnsRef.current.get(itemId) || latencyRef.current.turn || turnCounterRef.current || 0;
      const transcript = normalizeCaptionForDisplay(String(event.transcript || '')).trim();
      if (conversationTraceRef.current && transcript) {
        sendControlMessage({
          kind: 'desktop_user',
          turn,
          source: 'voice',
          text: transcript,
        });
      }
      if (itemId) userItemTurnsRef.current.delete(itemId);
    }
    if (type === 'response.function_call_arguments.done' && event.name === 'route_jarvis_turn') {
      try {
        const routed = JSON.parse(String(event.arguments || '{}'));
        const route = String(routed?.route || 'unknown');
        latencyRef.current.routeDecided ??= now;
        latencyRef.current.route = route;
        sendControlMessage({
          kind: 'desktop_route',
          turn: latencyRef.current.turn,
          call_id: String(event.call_id || ''),
          route,
          speech_end_to_route_ms:
            latencyRef.current.speechStopped === undefined
              ? null
              : Math.round(now - latencyRef.current.speechStopped),
        });
      } catch (_) { /* malformed routing telemetry still flows to Core for fail-closed handling */ }
    }
    // Route telemetry is intentionally sent first so Core can bind this call_id
    // to the visible turn before the matching function-call event starts work.
    forwardToCore(event);
    if (type === 'input_audio_buffer.speech_started') {
      clearIdleTimer();
      turnCounterRef.current += 1;
      latencyRef.current = { turn: turnCounterRef.current, speechStarted: now };
      setStateSafely('listening', 'I’m listening');
    } else if (type === 'input_audio_buffer.speech_stopped') {
      latencyRef.current.speechStopped = now;
      setStateSafely('thinking', 'Thinking');
      // Keep Semantic VAD for natural endpointing, but Jarvis owns response
      // creation so Core can attach a turn-specific compact response policy.
      requestNormalRealtimeResponse();
    } else if (type === 'response.created') {
      latencyRef.current.responseCreated ??= now;
      const responseId = responseIdForEvent(event);
      if (responseId) activeResponseIdRef.current = responseId;
      if (!responseId || !suppressedResponseIdsRef.current.has(responseId)) {
        if (audioRef.current) audioRef.current.muted = false;
      }
      clearCaptionPacing(true);
      setStateSafely('thinking', 'Thinking');
    } else if (type === 'response.output_item.added') {
      rememberResponseItem(event);
      if (event.item?.type === 'function_call' && event.item?.name === 'route_jarvis_turn') {
        clearIdleTimer();
        suppressTurnRouterOutput(event);
      } else if (event.item?.type === 'function_call' && event.item?.name === 'delegate_to_jarvis_core') {
        clearIdleTimer();
        suppressDelegationPreamble(event);
      }
    } else if (type === 'response.output_audio_transcript.delta') {
      if (responseIsSuppressed(event)) return;
      latencyRef.current.firstTranscript ??= now;
      enqueueCaptionDelta(event.delta || '');
    } else if (type === 'output_audio_buffer.started') {
      if (responseIsSuppressed(event)) {
        if (audioRef.current) audioRef.current.muted = true;
        const dc = dcRef.current;
        if (dc?.readyState === 'open') {
          try { dc.send(JSON.stringify({ type: 'output_audio_buffer.clear' })); } catch (_) { /* best effort */ }
        }
        return;
      }
      if (audioRef.current) audioRef.current.muted = false;
      clearIdleTimer();
      latencyRef.current.firstAudio ??= now;
      audioPlayingRef.current = true;
      captionAudioStartedRef.current = true;
      pumpCaption(45);
      setStateSafely('speaking', 'Speaking');
      if (!latencyRef.current.reported) {
        latencyRef.current.reported = true;
        sendLatencySummary();
      }
    } else if (type === 'output_audio_buffer.stopped') {
      if (responseIsSuppressed(event)) return;
      // WebRTC owns playout. Stay SPEAKING until its output buffer is actually drained.
      audioPlayingRef.current = false;
      if (captionTimerRef.current !== null) window.clearTimeout(captionTimerRef.current);
      captionTimerRef.current = null;
      captionIndexRef.current = captionSourceRef.current.length;
      if (captionSourceRef.current) setCaption(normalizeCaptionForDisplay(captionSourceRef.current));
      scheduleIdle(140);
      noteActivity();
    } else if (type === 'output_audio_buffer.cleared') {
      audioPlayingRef.current = false;
      clearCaptionPacing(false);
      setJarvisState((current) => current === 'speaking' ? 'idle' : current);
      noteActivity();
    } else if (type === 'response.function_call_arguments.done') {
      if (event.name === 'route_jarvis_turn') {
        clearIdleTimer();
        suppressTurnRouterOutput(event);
        try {
          const routed = JSON.parse(String(event.arguments || '{}'));
          if (routed?.route && !['direct', 'sleep'].includes(String(routed.route))) {
            setStateSafely('working', 'Working');
          }
        } catch (_) { /* routing schema is validated provider-side; keep Thinking on malformed telemetry */ }
      } else if (event.name === 'delegate_to_jarvis_core') {
        clearIdleTimer();
        suppressDelegationPreamble(event);
      }
    } else if (type === 'response.done') {
      const routingCall = event.response?.output?.find(
        (item) => item?.type === 'function_call' && item?.name === 'route_jarvis_turn',
      );
      const delegationCall = event.response?.output?.find(
        (item) => item?.type === 'function_call' && item?.name === 'delegate_to_jarvis_core',
      );
      const hasFunctionCall = Boolean(event.response?.output?.some((item) => item?.type === 'function_call'));
      if (routingCall) {
        // The first response is an internal text-only routing transaction. Nothing
        // from it belongs in the user-facing audio/caption surface or chat history.
        suppressTurnRouterOutput(event);
        deleteSuppressedResponseMessages(event);
      } else if (delegationCall) {
        // Provider-generated pre-tool speech is internal routing noise. It is intentionally
        // discarded rather than preserved; only the post-tool authoritative answer is visible/audible.
        suppressDelegationPreamble(event);
        // Wait until response.done before removing any generated assistant message item so
        // Realtime never receives an item-delete request for content that is still streaming.
        deleteSuppressedResponseMessages(event);
      } else if (hasFunctionCall) {
        clearCaptionPacing(true);
      } else if (event.response?.status === 'completed') {
        if (conversationTraceRef.current) {
          const text = responseTranscript(event.response) || normalizeCaptionForDisplay(captionSourceRef.current).trim();
          if (text) {
            sendControlMessage({
              kind: 'desktop_reply',
              turn: latencyRef.current.turn || turnCounterRef.current || 0,
              source: latencyRef.current.route === 'direct' ? 'realtime' : 'core',
              text,
            });
          }
        }
        captionResponseCompleteRef.current = true;
        captionShouldIdleRef.current = !audioPlayingRef.current && !captionAudioStartedRef.current;
        if (!captionAudioStartedRef.current) {
          captionAudioStartedRef.current = true;
          pumpCaption(120);
          scheduleIdle(220);
          noteActivity();
        } else {
          pumpCaption();
        }
        if (!latencyRef.current.reported) {
          latencyRef.current.reported = true;
          sendLatencySummary();
        }
      } else if (event.response?.status === 'cancelled') {
        // Drop caption text that was generated but never actually spoken after interruption.
        clearCaptionPacing(false);
        noteActivity();
      }
    } else if (type === 'error') {
      setStateSafely('error', event.error?.message || 'Realtime error');
    }
  };

  const startRealtimeSession = async (preservedCommand = '', reason = 'client_wake') => {
    if (stoppingRef.current) return;
    if (presenceRef.current === 'awake' && dcRef.current?.readyState === 'open') {
      if (preservedCommand) dispatchTextToRealtime(preservedCommand, 'wake_transcript');
      return;
    }
    await stopWakeListening();
    setPresenceSafely('awake');
    setStateSafely('waking', 'Waking');
    try {
      await fetch('/api/presence/wake', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason }),
      });
      const mic = await ensureMic();
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
        if (payload.kind === 'response_policy' && payload.response && typeof payload.response === 'object') {
          responsePolicyRef.current = payload.response as ResponsePolicy;
        } else if (payload.kind === 'realtime_send' && dcRef.current?.readyState === 'open') {
          dcRef.current.send(JSON.stringify(payload.event));
        } else if (payload.kind === 'lifecycle_command' && payload.command === 'sleep') {
          void enterSleep(String(payload.reason || 'voice_command'));
        } else if (payload.kind === 'lab_command' && payload.command === 'close') {
          void enterSleep('server_close');
        }
      };
      ws.onclose = () => {
        if (!realtimeClosingRef.current && presenceRef.current === 'awake' && !stoppingRef.current) {
          setStateSafely('error', 'Jarvis Core disconnected');
        }
      };

      const pc = new RTCPeerConnection();
      pcRef.current = pc;
      mic.getTracks().forEach((track) => pc.addTrack(track, mic));
      pc.ontrack = async (event) => {
        const remote = event.streams[0] || new MediaStream([event.track]);
        if (audioRef.current) {
          audioRef.current.muted = false;
          audioRef.current.srcObject = remote;
          try { await audioRef.current.play(); } catch (_) { /* autoplay enabled by Electron */ }
        }
      };
      pc.onconnectionstatechange = () => {
        if (pc.connectionState === 'connected' && !preservedCommand) {
          setStateSafely('idle', 'Ready');
          noteActivity();
        }
        if (['failed', 'disconnected'].includes(pc.connectionState) && presenceRef.current === 'awake' && !realtimeClosingRef.current) {
          setStateSafely('error', `WebRTC ${pc.connectionState}`);
        }
      };

      const dc = pc.createDataChannel('oai-events');
      dcRef.current = dc;
      dc.onmessage = (message) => {
        try { handleRealtimeEvent(JSON.parse(message.data)); } catch (_) { /* ignore malformed provider event */ }
      };

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
      await new Promise<void>((resolve, reject) => {
        if (dc.readyState === 'open') { resolve(); return; }
        const timeout = window.setTimeout(() => reject(new Error('Realtime data channel did not open')), 10_000);
        dc.onopen = () => { window.clearTimeout(timeout); resolve(); };
      });
      if (preservedCommand.trim()) {
        dispatchTextToRealtime(preservedCommand, 'wake_transcript');
      } else {
        setStateSafely('idle', 'Ready');
        noteActivity();
      }
    } catch (error) {
      setStateSafely('error', error instanceof Error ? error.message : String(error));
      await stopRealtimeSession();
      setPresenceSafely('sleeping');
      if (!stoppingRef.current) await startWakeListening();
    }
  };

  const stop = async () => {
    if (stoppingRef.current) return;
    stoppingRef.current = true;
    clearIdleTimer();
    clearCaptionPacing(false);
    await stopWakeListening();
    await stopRealtimeSession();
    micRef.current?.getTracks().forEach((track) => track.stop());
    micRef.current = null;
  };

  useEffect(() => {
    stoppingRef.current = false;
    const boot = async () => {
      try {
        const response = await fetch('/api/desktop/config');
        if (response.ok) {
          const config = await response.json();
          if (Number(config.idle_sleep_seconds) > 0) idleSleepSecondsRef.current = Number(config.idle_sleep_seconds);
          conversationTraceRef.current = config.conversation_trace !== false;
          const phrases = Array.isArray(config.wake_phrases) ? config.wake_phrases : [];
          if (phrases.length) wakePhraseRef.current = String(phrases[phrases.length - 1] || 'Jarvis');
        }
        setPresenceSafely('sleeping');
        await ensureMic();
        await startWakeListening();
      } catch (error) {
        setStateSafely('error', error instanceof Error ? error.message : String(error));
      }
    };
    void boot();
    const unload = () => { void stop(); };
    window.addEventListener('beforeunload', unload);
    return () => {
      window.removeEventListener('beforeunload', unload);
      void stop();
    };
    // One lifecycle controller owns one renderer microphone and swaps only the
    // local wake lane / Realtime lane beneath it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCaptionScroll = () => {
    const viewport = captionViewportRef.current;
    if (!viewport) return;
    const distanceFromBottom = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight;
    const nearLatest = distanceFromBottom <= 24;
    captionStickToLatestRef.current = nearLatest;
    setCaptionBrowsing(!nearLatest);
  };

  useEffect(() => {
    const viewport = captionViewportRef.current;
    if (!viewport) return;
    const frame = window.requestAnimationFrame(() => {
      const overflow = viewport.scrollHeight > viewport.clientHeight + 4;
      setCaptionOverflow(overflow);
      if (captionStickToLatestRef.current) {
        viewport.scrollTop = viewport.scrollHeight;
        setCaptionBrowsing(false);
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [caption]);

  useEffect(() => {
    if (!transcriptExpanded) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setTranscriptExpanded(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [transcriptExpanded]);

  const submitText = (event: FormEvent) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text || jarvisState === 'connecting' || jarvisState === 'waking' || jarvisState === 'error') return;
    setDraft('');
    if (presenceRef.current === 'sleeping') {
      void startRealtimeSession(text, 'typed_wake');
      return;
    }
    const dc = dcRef.current;
    if (!dc || dc.readyState !== 'open') return;
    if (jarvisState === 'speaking') {
      dc.send(JSON.stringify({ type: 'response.cancel' }));
      dc.send(JSON.stringify({ type: 'output_audio_buffer.clear' }));
    }
    dispatchTextToRealtime(text, 'typed');
  };

  const isUnavailable = jarvisState === 'connecting' || jarvisState === 'waking' || jarvisState === 'error';
  const placeholder = jarvisState === 'error'
    ? 'Jarvis is offline'
    : presence === 'sleeping'
      ? 'Type to wake Jarvis…'
      : 'Ask Jarvis…';
  const hint = presence === 'sleeping'
    ? `Say “${wakePhraseRef.current}” to wake me, or type instead.`
    : 'Speak naturally, or type instead.';

  return (
    <main className={`shell shell--${presence}`}>
      <section className="jarvis" aria-live="polite">
        <header className="brand">
          <span className={`brand__dot brand__dot--${jarvisState}`} />
          <span>JARVIS</span>
        </header>

        <ParticleOrb state={jarvisState} />

        <div className="state-label">{stateLabels[jarvisState]}</div>
        <div className={`caption-frame ${captionOverflow ? 'caption-frame--overflow' : ''} ${captionBrowsing ? 'caption-frame--browsing' : ''}`}>
          <div ref={captionViewportRef} className="caption__viewport" aria-live="polite" onScroll={handleCaptionScroll}>
            <div className={`caption ${caption ? 'caption--active' : ''}`}>
              {caption || (jarvisState === 'error' ? detail : '\u00A0')}
            </div>
          </div>
          {captionOverflow && caption ? (
            <button
              type="button"
              className="caption-expand"
              aria-label="Expand full response text"
              title="Expand response"
              onClick={() => setTranscriptExpanded(true)}
            >
              ↗
            </button>
          ) : null}
        </div>

        <form className="composer" onSubmit={submitText}>
          <input
            aria-label="Type to Jarvis"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={placeholder}
            disabled={isUnavailable}
            autoComplete="off"
          />
          <button type="submit" disabled={!draft.trim() || isUnavailable} aria-label="Send">
            <span>↗</span>
          </button>
        </form>

        <p className="hint">{hint}</p>

        {transcriptExpanded ? (
          <div className="transcript-overlay" role="dialog" aria-modal="true" aria-label="Full Jarvis response">
            <div className="transcript-overlay__panel">
              <div className="transcript-overlay__header">
                <span>JARVIS RESPONSE</span>
                <button type="button" onClick={() => setTranscriptExpanded(false)} aria-label="Close full response">×</button>
              </div>
              <div className="transcript-overlay__body">{caption}</div>
            </div>
          </div>
        ) : null}

        <audio ref={audioRef} autoPlay />
      </section>
    </main>
  );
}
