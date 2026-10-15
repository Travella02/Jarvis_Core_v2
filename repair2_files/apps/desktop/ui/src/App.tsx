import { FormEvent, useEffect, useRef, useState } from 'react';
import { StreamingPcmGate } from './streamingPcmGate';
import { playLunaHoldCue } from './lunaCancelCue';
import { isVerifiedSleepEvidence, hasSubstantiveUserWords, type SleepTurnInput } from './sleepAuthorization';

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
  call_id?: string;
  arguments?: string;
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
  error?: { message?: string; code?: string };
  response?: { id?: string; status?: string; status_details?: {reason?: string}; output?: RealtimeItem[]; metadata?: Record<string, string>; usage?: { output_token_details?: { text_tokens?: number; audio_tokens?: number } } };
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
  const [cancelHoldTurn, setCancelHoldTurn] = useState<number | null>(null);
  const cancelHoldTurnRef = useRef<number | null>(null);
  useEffect(() => { cancelHoldTurnRef.current = cancelHoldTurn; }, [cancelHoldTurn]);
  useEffect(() => {
    if (cancelHoldTurn === null) return;
    // The same eight-second diagnostic hold used by the host; don't leave
    // a stale banner in the event of a disconnected WebSocket.
    const timeout = window.setTimeout(() => setCancelHoldTurn(null), 10500);
    return () => window.clearTimeout(timeout);
  }, [cancelHoldTurn]);

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
  const wakeGenerationRef = useRef(0);
  const captionSourceRef = useRef('');
  const captionIndexRef = useRef(0);
  const captionTimerRef = useRef<number | null>(null);
  const captionResponseCompleteRef = useRef(false);
  const captionShouldIdleRef = useRef(false);
  const captionAudioStartedRef = useRef(false);
  const audioPlayingRef = useRef(false);
  const turnCounterRef = useRef(0);
  // A wake-only acknowledgment is a normal, fully authorized Realtime turn,
  // with a shorter speech instruction. Do not treat wake+command as wake-only.
  const wakeOnlyTurnRef = useRef(0);
  const responsePolicyRef = useRef<ResponsePolicy | null>(null);
  const activeResponseIdRef = useRef('');
  const suppressedResponseIdsRef = useRef<Set<string>>(new Set());
  const responseMessageItemIdsRef = useRef<Map<string, Set<string>>>(new Map());
  const userItemTurnsRef = useRef<Map<string, number>>(new Map());
  const conversationTraceRef = useRef(true);
  const parallelShadowEnabledRef = useRef(false);
  const directOnlyBenchmarkRef = useRef(false);
  const toolProbeRef = useRef(false);
  const bufferedToolProbeRef = useRef(false);
  const overlapProbeRef = useRef(false);
  const coreLunaProbeRef = useRef(false);
  const coreActionsProbeRef = useRef(false);
  const delegationGuidanceRef = useRef(false); // Opt-in; no extra inference request.
  const overlapCandidateStageRef = useRef('overlap_candidate');
  const overlapGateRef = useRef<StreamingPcmGate | null>(null);
  const pcmTrimRef = useRef(false);
  const overlapDecisionIdRef = useRef('');
  const overlapCandidateIdRef = useRef('');
  const overlapDecisionRef = useRef<'pending' | 'direct' | 'tool' | 'failed'>('pending');
  const overlapCandidateDoneRef = useRef(false);
  const overlapAudioDrainedRef = useRef(false);
  const overlapAudioStartedRef = useRef(false);
  const overlapReplyRef = useRef('');
  // The Core-verified text remains available if Realtime speech synthesis fails.
  const coreLunaVerifiedTextRef = useRef('');
  const overlapEpochRef = useRef(0);
  const overlapStartedRef = useRef(0);
  const overlapDecisionMsRef = useRef<number | null>(null);
  const overlapPerfRef = useRef<{turn:number;commit:number|null;transcript:number|null;
    route:number|null;candidate:number|null;pcmReady:number|null;gateAuthorized:number|null;
    pcmSignal:number|null;pcmBufferReady:number|null}>({
      turn:0,commit:null,transcript:null,route:null,candidate:null,pcmReady:null,gateAuthorized:null,
      pcmSignal:null,pcmBufferReady:null});
  // An out-of-band response must explicitly reference the committed USER item.
  // speech_stopped alone is too early: the model may otherwise see the prior turn.
  const overlapCommittedItemRef = useRef('');
  const overlapAwaitingCommitRef = useRef(false);
  const overlapCommitTimerRef = useRef<number | null>(null);
  const overlapActiveTurnRef = useRef(0);
  // Sleep evidence is authorized only from a confirmed transcript tied to the
  // same committed Realtime audio item (or from explicitly submitted text).
  const overlapInputBindingRef = useRef('');
  const overlapSleepInputRef = useRef<SleepTurnInput | null>(null);
  const overlapTranscriptsRef = useRef<Map<string, string>>(new Map());
  const overlapPendingSleepRef = useRef<{turn:number;epoch:number;evidence:string} | null>(null);
  const overlapPendingActionRef = useRef<{turn:number;epoch:number} | null>(null);
  const overlapActionTimerRef = useRef<number | null>(null);
  // An action selection is not finished until the CURRENT turn receives Core's
  // authoritative result (or the UI times out). Never retry an ambiguous launch.
  const overlapAwaitingActionResultRef = useRef<{turn:number;epoch:number} | null>(null);
  const overlapActionResultTimerRef = useRef<number | null>(null);
  const overlapSleepTimerRef = useRef<number | null>(null);
  const overlapDirectVerifiedRef = useRef(false);
  const overlapDirectTimerRef = useRef<number | null>(null);
  const bufferedRemoteStreamRef = useRef<MediaStream | null>(null);
  const bufferedCaptureRef = useRef<MediaRecorder | null>(null);
  const bufferedChunksRef = useRef<Blob[]>([]);
  const bufferedRecordingStartedRef = useRef(0);
  const bufferedAudioStartedRef = useRef(0);
  const bufferedAudioSeenRef = useRef(false);
  const bufferedResponseIdRef = useRef('');
  const bufferedReplyRef = useRef('');
  const bufferedOutcomeRef = useRef<'unknown' | 'approved' | 'tool' | 'blocked'>('unknown');
  const bufferedPendingToolRef = useRef<RealtimeItem[]>([]);
  const bufferedWasFollowupRef = useRef(false);
  const bufferedFollowupNextRef = useRef(false);
  // WebRTC output-buffer drain may arrive before OR after response.done.
  const bufferedOutputDrainedRef = useRef(false);
  const bufferedFinalizeQueuedRef = useRef(false);
  const bufferedPlayerRef = useRef<HTMLAudioElement | null>(null);
  const bufferedPlaybackUrlRef = useRef('');
  const bufferedEpochRef = useRef(0);
  const bufferedTimeoutRef = useRef<number | null>(null);
  const toolProbeTextRef = useRef('');
  const toolProbePretoolTextRef = useRef('');
  const parallelShadowIdsRef = useRef<Map<string, { turn: number; started: number; firstToken?: number }>>(new Map());
  const parallelShadowRequestedRef = useRef<Map<number, number>>(new Map());
  const parallelShadowPendingCancelRef = useRef<Set<number>>(new Set());
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
    // Invalidate all callbacks/timeouts from the old socket before closing it.
    // Its asynchronous onclose event must never resurrect an obsolete listener.
    wakeGenerationRef.current += 1;
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
    // Socket readiness alone is not microphone readiness. Let the local host
    // report the distinction while investigating wake failures on Windows.
    if (ws.readyState === WebSocket.OPEN && presenceRef.current === 'sleeping') {
      ws.send(JSON.stringify({ kind: 'wake_audio_tap_ready' }));
    }
  };

  const startWakeListening = async () => {
    if (stoppingRef.current || presenceRef.current !== 'sleeping') return;
    await stopWakeListening();
    const generation = wakeGenerationRef.current;
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
        void startWakeAudioTap(ws).catch((error) => {
          const detail = error instanceof Error ? error.message : String(error);
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ kind: 'wake_audio_tap_error', detail }));
          }
          if (wakeGenerationRef.current === generation && presenceRef.current === 'sleeping') {
            setStateSafely('error', `Local wake microphone unavailable: ${detail}`);
          }
        });
      } else if (payload.kind === 'wake_detected') {
        const command = String(payload.command_text || '').trim();
        if (command) {
          // Same-turn wake+command path: no preliminary greeting.
          void startRealtimeSession(command, 'local_wake_phrase');
        } else {
          // The host sends this only after LocalWakeListener verifies a complete
          // wake-only utterance. Use the exact transcript, not canned assistant audio.
          const wakeOnly = String(payload.wake_only_transcript || '').trim();
          void startRealtimeSession(wakeOnly, wakeOnly ? 'wake_only' : 'local_wake_phrase');
        }
      } else if (payload.kind === 'wake_unavailable') {
        setStateSafely('sleeping', 'Voice wake is unavailable; type a message to wake Jarvis.');
      }
    };
    ws.onclose = () => {
      if (wakeGenerationRef.current !== generation || wakeWsRef.current !== ws) return;
      wakeWsRef.current = null;
      if (!wakeClosingRef.current && presenceRef.current === 'sleeping' && !stoppingRef.current) {
        window.setTimeout(() => {
          if (wakeGenerationRef.current === generation && presenceRef.current === 'sleeping' && !stoppingRef.current) {
            void startWakeListening();
          }
        }, 650);
      }
    };
  };

  // Repair6 experimental gated-publication recorder. Unlike muting after a
  // function call, the *entire incoming WebRTC track* is muted from ontrack onward.
  // A response owns no playback/captions until response.done is authoritative.
  const stopBufferedPlayback = () => {
    bufferedEpochRef.current += 1;
    const player = bufferedPlayerRef.current;
    if (player) {
      player.pause();
      player.removeAttribute('src');
      player.load();
    }
    bufferedPlayerRef.current = null;
    if (bufferedPlaybackUrlRef.current) URL.revokeObjectURL(bufferedPlaybackUrlRef.current);
    bufferedPlaybackUrlRef.current = '';
    audioPlayingRef.current = false;
  };

  const discardBufferedCapture = () => {
    if (bufferedTimeoutRef.current !== null) window.clearTimeout(bufferedTimeoutRef.current);
    bufferedTimeoutRef.current = null;
    const recorder = bufferedCaptureRef.current;
    bufferedCaptureRef.current = null;
    bufferedChunksRef.current = [];
    if (recorder && recorder.state !== 'inactive') {
      recorder.ondataavailable = null;
      recorder.onstop = null;
      try { recorder.stop(); } catch (_) { /* release best effort */ }
    }
  };

  const resetBufferedTurn = () => {
    discardBufferedCapture();
    stopBufferedPlayback();
    bufferedOutcomeRef.current = 'blocked';
    bufferedPendingToolRef.current = [];
    bufferedResponseIdRef.current = '';
    bufferedReplyRef.current = '';
    bufferedAudioSeenRef.current = false;
    bufferedFollowupNextRef.current = false;
    bufferedOutputDrainedRef.current = false;
    bufferedFinalizeQueuedRef.current = false;
  };

  const beginBufferedCapture = (responseId: string) => {
    discardBufferedCapture();
    bufferedResponseIdRef.current = responseId;
    bufferedChunksRef.current = [];
    bufferedReplyRef.current = '';
    bufferedOutcomeRef.current = 'unknown';
    bufferedAudioSeenRef.current = false;
    bufferedAudioStartedRef.current = 0;
    bufferedOutputDrainedRef.current = false;
    bufferedFinalizeQueuedRef.current = false;
    bufferedWasFollowupRef.current = bufferedFollowupNextRef.current;
    bufferedFollowupNextRef.current = false;
    const stream = bufferedRemoteStreamRef.current;
    if (!stream || typeof MediaRecorder === 'undefined') {
      bufferedOutcomeRef.current = 'blocked';
      sendControlMessage({kind:'desktop_buffered_audio',turn:latencyRef.current.turn,phase:'capture_unavailable',reason:'missing_media_recorder_or_remote_stream'});
      return;
    }
    try {
      const preferred = 'audio/webm;codecs=opus';
      const options = MediaRecorder.isTypeSupported(preferred) ? { mimeType: preferred } : undefined;
      const recorder = new MediaRecorder(stream, options);
      bufferedCaptureRef.current = recorder;
      bufferedRecordingStartedRef.current = performance.now();
      recorder.ondataavailable = (evt: BlobEvent) => {
        if (bufferedCaptureRef.current === recorder && evt.data.size > 0) bufferedChunksRef.current.push(evt.data);
      };
      recorder.start(200);
      // Bound private audio retention; fail closed rather than silently play an
      // arbitrarily long speculative response or retain it indefinitely.
      bufferedTimeoutRef.current = window.setTimeout(() => {
        if (bufferedCaptureRef.current !== recorder) return;
        bufferedOutcomeRef.current = 'blocked';
        discardBufferedCapture();
        sendControlMessage({kind:'desktop_buffered_audio',turn:latencyRef.current.turn,phase:'capture_timeout',reason:'30_second_bound'});
      }, 30000);
    } catch (error) {
      bufferedOutcomeRef.current = 'blocked';
      sendControlMessage({kind:'desktop_buffered_audio',turn:latencyRef.current.turn,phase:'capture_error',reason:String(error)});
    }
  };

  const completeBufferedCapture = (approved: boolean) => {
    if (bufferedTimeoutRef.current !== null) window.clearTimeout(bufferedTimeoutRef.current);
    bufferedTimeoutRef.current = null;
    const recorder = bufferedCaptureRef.current;
    const id = bufferedResponseIdRef.current;
    const epoch = bufferedEpochRef.current;
    if (!recorder || recorder.state === 'inactive') {
      discardBufferedCapture();
      return;
    }
    const turn = latencyRef.current.turn;
    const reply = bufferedReplyRef.current;
    const wasFollowup = bufferedWasFollowupRef.current;
    const audioOffset = bufferedAudioStartedRef.current > bufferedRecordingStartedRef.current
      ? Math.max(0, (bufferedAudioStartedRef.current - bufferedRecordingStartedRef.current) / 1000 - 0.1)
      : 0;
    recorder.onstop = () => {
      if (bufferedCaptureRef.current !== recorder) return;
      const chunks = bufferedChunksRef.current;
      bufferedCaptureRef.current = null;
      bufferedChunksRef.current = [];
      if (!approved || !chunks.length || epoch !== bufferedEpochRef.current || id !== bufferedResponseIdRef.current) return;
      const blob = new Blob(chunks, {type:recorder.mimeType || 'audio/webm'});
      if (!blob.size) return;
      const url = URL.createObjectURL(blob);
      bufferedPlaybackUrlRef.current = url;
      const player = new Audio(url);
      bufferedPlayerRef.current = player;
      player.onloadedmetadata = () => {
        if (epoch !== bufferedEpochRef.current) return;
        if (Number.isFinite(player.duration) && player.duration > audioOffset + 0.05) {
          try { player.currentTime = audioOffset; } catch (_) { /* seek optional */ }
        }
        void player.play().catch(() => setStateSafely('error', 'Buffered audio playback unavailable'));
      };
      player.onplaying = () => {
        if (epoch !== bufferedEpochRef.current) return;
        latencyRef.current.firstAudio ??= performance.now();
        if (!latencyRef.current.reported) { latencyRef.current.reported = true; sendLatencySummary(); }
        audioPlayingRef.current = true;
        setStateSafely('speaking', 'Speaking');
        sendControlMessage({kind:'desktop_buffered_audio',turn,phase:'released',selected:wasFollowup?'verified_followup':'direct',
          capture_ms:Math.round(performance.now()-bufferedRecordingStartedRef.current),
          first_playback_ms:latencyRef.current.speechStopped===undefined?null:Math.round(performance.now()-latencyRef.current.speechStopped)});
        if (reply) {
          setCaption(reply);
          sendControlMessage({kind:'desktop_reply',turn,source:wasFollowup?'simulated_tool_result':'realtime',text:reply});
        }
      };
      player.onended = () => {
        if (epoch !== bufferedEpochRef.current) return;
        stopBufferedPlayback();
        scheduleIdle(180);
      };
    };
    try { recorder.stop(); } catch (_) { discardBufferedCapture(); }
  };

  const cancelOverlap = () => {
    if (overlapDirectTimerRef.current !== null) window.clearTimeout(overlapDirectTimerRef.current);
    overlapDirectTimerRef.current = null;
    overlapDirectVerifiedRef.current = false;
    if (overlapSleepTimerRef.current !== null) window.clearTimeout(overlapSleepTimerRef.current);
    overlapSleepTimerRef.current = null;
    overlapPendingSleepRef.current = null;
    if (overlapActionTimerRef.current !== null) window.clearTimeout(overlapActionTimerRef.current);
    overlapActionTimerRef.current = null;
    overlapPendingActionRef.current = null;
    if (overlapActionResultTimerRef.current !== null) window.clearTimeout(overlapActionResultTimerRef.current);
    overlapActionResultTimerRef.current = null;
    overlapAwaitingActionResultRef.current = null;
    overlapInputBindingRef.current = '';
    overlapSleepInputRef.current = null;
    if (coreLunaProbeRef.current && overlapActiveTurnRef.current) {
      sendControlMessage({kind:'desktop_luna_cancel',turn:overlapActiveTurnRef.current});
    }

    overlapEpochRef.current += 1;
    if (overlapCommitTimerRef.current !== null) window.clearTimeout(overlapCommitTimerRef.current);
    overlapCommitTimerRef.current = null;
    overlapAwaitingCommitRef.current = false;
    overlapCommittedItemRef.current = '';
    overlapActiveTurnRef.current = 0;
    overlapGateRef.current?.abort();
    overlapGateRef.current = null;
    const oldCandidate = overlapCandidateIdRef.current;
    const oldDone = overlapCandidateDoneRef.current;
    overlapDecisionIdRef.current = '';
    overlapCandidateIdRef.current = '';
    overlapDecisionRef.current = 'pending';
    overlapDirectVerifiedRef.current = false;
    if (overlapDirectTimerRef.current !== null) window.clearTimeout(overlapDirectTimerRef.current);
    overlapDirectTimerRef.current = null;
    overlapCandidateStageRef.current = 'overlap_candidate';
    overlapCandidateDoneRef.current = false;
    overlapAudioDrainedRef.current = false;
    overlapAudioStartedRef.current = false;
    overlapReplyRef.current = '';
    coreLunaVerifiedTextRef.current = '';
    const dc = dcRef.current;
    if (dc?.readyState === 'open') {
      // Response-scoped cancellation is required: never let a previous turn publish.
      // Browser audio remains muted even if cancellation is delayed.
      // Do not cancel a shared/default response from another mode.
      if (oldCandidate && !oldDone) {
        dc.send(JSON.stringify({type:'response.cancel',response_id:oldCandidate}));
      }
      if (oldCandidate) dc.send(JSON.stringify({type:'output_audio_buffer.clear'}));
    }
  };

  const silenceRealtimeOutput = () => {
    resetBufferedTurn();
    cancelOverlap();
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
    setCancelHoldTurn(null);
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
    wakeOnlyTurnRef.current = 0;
    suppressedResponseIdsRef.current.clear();
    responseMessageItemIdsRef.current.clear();
    parallelShadowIdsRef.current.clear();
    parallelShadowRequestedRef.current.clear();
    parallelShadowPendingCancelRef.current.clear();
    parallelShadowEnabledRef.current = false;
    bufferedToolProbeRef.current = false;
    bufferedRemoteStreamRef.current = null;
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

  const requestOverlapResponses = (
    dc: RTCDataChannel | null = dcRef.current,
    committedItemId = '',
    typedText = '',
  ) => {
    if (!dc || dc.readyState !== 'open') return;
    // Constrain BOTH speculative responses to the identical current-turn input.
    // Out-of-band output isolation does not constrain the response input context.
    const input = committedItemId
      ? [{type:'item_reference',id:committedItemId}]
      : typedText.trim()
        ? [{type:'message',role:'user',content:[{type:'input_text',text:typedText.trim()}]}]
        : [];
    if (!input.length || (committedItemId && !/^item_[A-Za-z0-9_-]+$/.test(committedItemId))) {
      sendControlMessage({kind:'desktop_overlap_audio',turn:latencyRef.current.turn,phase:'error',reason:'missing_confirmed_user_item'});
      setStateSafely('error','Could not confirm the current voice turn');
      return;
    }
    if (overlapCommitTimerRef.current !== null) window.clearTimeout(overlapCommitTimerRef.current);
    overlapCommitTimerRef.current = null;
    overlapAwaitingCommitRef.current = false;
    overlapActiveTurnRef.current = latencyRef.current.turn;
    overlapInputBindingRef.current = committedItemId || `typed:${latencyRef.current.turn}`;
    const cachedTranscript = committedItemId ? overlapTranscriptsRef.current.get(committedItemId) : null;
    overlapSleepInputRef.current = typedText.trim()
      ? {turn:latencyRef.current.turn,binding:overlapInputBindingRef.current,source:'typed',text:typedText.trim()}
      : cachedTranscript
        ? {turn:latencyRef.current.turn,binding:overlapInputBindingRef.current,source:'voice',text:cachedTranscript}
        : null;
    overlapDecisionRef.current = 'pending';
    overlapCandidateStageRef.current = 'overlap_candidate';
    overlapDecisionIdRef.current = '';
    overlapCandidateIdRef.current = '';
    overlapReplyRef.current = '';
    overlapCandidateDoneRef.current = false;
    overlapAudioDrainedRef.current = false;
    overlapAudioStartedRef.current = false;
    overlapStartedRef.current = performance.now();
    overlapPerfRef.current = {turn:latencyRef.current.turn,
      commit:overlapStartedRef.current,transcript:overlapSleepInputRef.current ? overlapStartedRef.current : null,
      route:null,candidate:null,pcmReady:null,gateAuthorized:null,pcmSignal:null,pcmBufferReady:null};
    overlapDecisionMsRef.current = null;
    latencyRef.current.route = 'overlap_stream_probe';
    latencyRef.current.routeDecided = undefined;
    setStateSafely('thinking', 'Preparing response');
    const turn = String(latencyRef.current.turn);
    const wakeOnly = wakeOnlyTurnRef.current === latencyRef.current.turn;
    const tools = responsePolicyRef.current?.tools || [];
    // Both responses are OUT OF BAND; neither can mutate the default history.
    // The silent decision is the only response allowed to request probe tools.
    dc.send(JSON.stringify({type:'response.create',response:{conversation:'none',
      metadata:{jarvis_stage:'overlap_decision',jarvis_turn:turn},
      input,
      output_modalities:['text'],max_output_tokens:512,tools,tool_choice:'auto',
      instructions:(coreLunaProbeRef.current
        ? `Classify the entire current user utterance, including its ending. A clear closing or dismissal takes precedence over polite words earlier in the same utterance. For example, "Thanks, Jarvis" is ordinary gratitude (direct); "Thanks Jarvis, that is all" or "Thanks Jarvis, that's all" is an explicit ending (sleep_jarvis); "Thanks, one more question" is continuing conversation (direct); and "What does the expression that's all mean?" is a question (direct). Do not mistake a quotation or negated instruction for an actual dismissal. For sleep, call sleep_jarvis as your only output; never speak, send farewell text, or issue another tool. Set sleep_evidence to the exact contiguous closing words in the user input, not invented or paraphrased words. Mere gratitude does not authorize sleep. The desktop separately checks the quoted evidence against the confirmed same-turn transcript. For complex reasoning or coding use ask_luna, which may invoke real Core reasoning after authorization. For an explicit request to open YouTube, select test_action (immediate). This opt-in trial may execute only if Core independently confirms the matching user command. All other external actions remain dry runs. Never claim work was executed prematurely.`
        : `Classify the entire current user utterance, including its ending. A clear closing or dismissal takes precedence over polite words earlier in the same utterance. For example, "Thanks, Jarvis" is ordinary gratitude (direct); "Thanks Jarvis, that is all" or "Thanks Jarvis, that's all" is an explicit ending (sleep_jarvis); "Thanks, one more question" is continuing conversation (direct); and "What does the expression that's all mean?" is a question (direct). Do not mistake a quotation or negated instruction for an actual dismissal. For sleep, call sleep_jarvis as your only output; never speak, send farewell text, or issue another tool. Set sleep_evidence to the exact contiguous closing words in the user input, not invented or paraphrased words. Mere gratitude does not authorize sleep. The desktop separately checks the quoted evidence against the confirmed same-turn transcript. Otherwise decide direct versus ask_luna for complex reasoning or test_action for external actions. Both expert/action tools are dry runs. Never claim any action succeeded.`)
        + (delegationGuidanceRef.current && coreLunaProbeRef.current && !wakeOnly
          ? ' In this experimental A/B arm, choose ask_luna for user requests requiring substantial multi-step reasoning, a detailed technical design, trade-off analysis across multiple constraints, or a considered recommendation—even when the user does not explicitly mention Core, Luna, or deep reasoning. Choose direct for greetings, simple arithmetic, straightforward factual questions, a short definition, and light conversation. Do not escalate merely because a familiar technical word occurs; judge the entire user request and expected answer. This is guidance to the same Mini router, NOT an additional model call. Preserve sleep_evidence validation and external-action dry-run rules exactly.'
          : '')
        + (wakeOnly ? ' This is a locally verified wake-only name call with no requested action. Route direct for a brief greeting; do not delegate it, put Jarvis to sleep, or perform an action.' : '')}}));
    dc.send(JSON.stringify({type:'response.create',response:{conversation:'none',
      metadata:{jarvis_stage:'overlap_candidate',jarvis_turn:turn},
      input,
      output_modalities:['audio'],max_output_tokens:1024,tools:[],tool_choice:'none',
      instructions:wakeOnly
        ? 'The user just called you by name to wake you. Reply naturally in 1 to 5 spoken words, as a brief acknowledgment. Vary your wording. No explanations, tools, actions, preambles, or claims of external work.'
        : 'Generate one natural conversational answer without tools. Do not claim external actions or research were performed. No action is executable in this response.'}}));
    sendControlMessage({kind:'desktop_overlap_audio',turn:latencyRef.current.turn,phase:'started',
      input_binding:committedItemId ? 'committed_audio_item' : 'typed_text',
      commit_wait_ms:latencyRef.current.speechStopped === undefined ? null : Math.round(performance.now()-latencyRef.current.speechStopped)});
  };

  const awaitOverlapAudioCommit = () => {
    overlapAwaitingCommitRef.current = true;
    if (overlapCommittedItemRef.current) {
      requestOverlapResponses(dcRef.current, overlapCommittedItemRef.current);
      return;
    }
    const epoch = overlapEpochRef.current;
    const turn = latencyRef.current.turn;
    overlapCommitTimerRef.current = window.setTimeout(() => {
      if (epoch !== overlapEpochRef.current || !overlapAwaitingCommitRef.current) return;
      overlapAwaitingCommitRef.current = false;
      overlapCommitTimerRef.current = null;
      sendControlMessage({kind:'desktop_overlap_audio',turn,phase:'error',reason:'input_commit_timeout'});
      setStateSafely('error','Speech input was not committed');
    }, 2000);
  };

  const requestParallelShadow = (dc: RTCDataChannel | null = dcRef.current) => {
    if (!parallelShadowEnabledRef.current || dc?.readyState !== 'open') return;
    const turn = latencyRef.current.turn || turnCounterRef.current;
    // Response is *text only*, side-effect free and outside conversation.
    // This first experiment deliberately never generates unplayable/unbuffered
    // audio. We only want to validate response overlap and token costs.
    parallelShadowRequestedRef.current.set(turn, performance.now());
    dc.send(JSON.stringify({
      type: 'response.create',
      response: {
        conversation: 'none',
        metadata: { jarvis_stage: 'parallel_shadow', jarvis_turn: String(turn) },
        output_modalities: ['text'],
        max_output_tokens: 96,
        tools: [],
        tool_choice: 'none',
        instructions: 'Privately prepare one very short informational answer to the latest user utterance. Never call tools, execute actions, or claim actions succeeded. This is a hidden speculative test. Do not mention routing or backend systems.',
      },
    }));
  };

  const cancelParallelShadows = (turn: number) => {
    parallelShadowPendingCancelRef.current.add(turn);
    if (parallelShadowPendingCancelRef.current.size > 24) {
      parallelShadowPendingCancelRef.current = new Set(Array.from(parallelShadowPendingCancelRef.current).slice(-12));
    }
    const dc = dcRef.current;
    if (!dc || dc.readyState !== 'open') return;
    for (const [id, candidate] of parallelShadowIdsRef.current) {
      if (candidate.turn === turn) {
        // Response-specific cancellation, never cancel the main router.
        dc.send(JSON.stringify({ type: 'response.cancel', response_id: id }));
      }
    }
  };

  const dispatchTextToRealtime = (text: string, source = 'typed', wakeOnly = false) => {
    const dc = dcRef.current;
    const clean = text.trim();
    if (!clean || !dc || dc.readyState !== 'open') return false;
    if (overlapProbeRef.current) cancelOverlap(); // A typed turn replaces any in-flight speculative speech.
    turnCounterRef.current += 1;
    wakeOnlyTurnRef.current = wakeOnly ? turnCounterRef.current : 0;
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
    if (toolProbeRef.current) {
      latencyRef.current.route = 'tool_probe';
      latencyRef.current.routeDecided = now;
    } else if (bufferedToolProbeRef.current) {
      latencyRef.current.route = 'buffered_tool_probe';
      latencyRef.current.routeDecided = now;
    }
    if (directOnlyBenchmarkRef.current) {
      latencyRef.current.route = 'direct_no_gate';
      latencyRef.current.routeDecided = now;
      sendControlMessage({ kind: 'desktop_fast_direct', turn: turnCounterRef.current });
    }
    if (overlapProbeRef.current) requestOverlapResponses(dc, '', clean);
    else requestNormalRealtimeResponse(dc);
    if (overlapProbeRef.current || toolProbeRef.current || bufferedToolProbeRef.current) { /* Neither probe spawns shadows. */ }
    else if (!directOnlyBenchmarkRef.current) requestParallelShadow(dc);
    noteActivity();
    return true;
  };

  const launchBufferedFollowup = () => {
    if (bufferedOutcomeRef.current !== 'tool') return;
    const dc = dcRef.current;
    if (dc?.readyState !== 'open') return;
    const calls = bufferedPendingToolRef.current;
    bufferedPendingToolRef.current = [];
    bufferedOutcomeRef.current = 'blocked'; // One-shot: never dispatch twice.
    for (const call of calls) {
      const name = String(call.name || 'unknown');
      const permitted = name === 'ask_luna' || name === 'test_action';
      sendControlMessage({kind:'desktop_tool_probe',turn:latencyRef.current.turn,tool:name,phase:'selection',
        pretool_text_chars:bufferedReplyRef.current.length,
        decision_ms:latencyRef.current.speechStopped===undefined?null:Math.round(performance.now()-latencyRef.current.speechStopped)});
      const result = !permitted
        ? {status:'blocked',executed:false,message:'Unrecognized tool in isolated audio test.'}
        : name === 'ask_luna'
          ? {status:'not_executed',executed:false,message:'Luna was selected but not executed in this dry-run.'}
          : {status:'unavailable',executed:false,message:'The simulated background action did not start.'};
      if (call.call_id) dc.send(JSON.stringify({type:'conversation.item.create',item:{type:'function_call_output',call_id:call.call_id,output:JSON.stringify(result)}}));
    }
    bufferedFollowupNextRef.current = true;
    dc.send(JSON.stringify({type:'response.create',response:{max_output_tokens:1024,output_modalities:['audio'],tools:[],tool_choice:'none',
      instructions:'Speak a single short sentence (maximum 25 words) reporting the simulated result. No task was started and Luna did not actually run. Never claim success or execution.',
      metadata:{jarvis_stage:'buffered_tool_followup',jarvis_turn:String(latencyRef.current.turn)}}}));
  };

  const finalizeBufferedIfReady = () => {
    if (!bufferedOutputDrainedRef.current) return;
    if (bufferedOutcomeRef.current === 'tool') {
      // No pre-tool audio is ever authorized, including when the drain event
      // arrived before response.done. Launch the dry-run follow-up once.
      launchBufferedFollowup();
      return;
    }
    if (bufferedOutcomeRef.current === 'approved') {
      if (bufferedFinalizeQueuedRef.current) return;
      bufferedFinalizeQueuedRef.current = true;
      const epoch = bufferedEpochRef.current;
      window.setTimeout(() => {
        if (epoch === bufferedEpochRef.current && bufferedOutcomeRef.current === 'approved') {
          completeBufferedCapture(true);
        }
      }, 120);
    }
  };

  const recoverIncompleteDirectResponse = (turn: number, reason: string) => {
    // Direct speech is optional output, not a connectivity health check.
    // A max_output_tokens limit (or transient renderer failure) must never
    // disable a still-connected, awake Jarvis desktop session.
    if (!overlapProbeRef.current || turn !== overlapActiveTurnRef.current ||
        overlapCandidateStageRef.current !== 'overlap_candidate' ||
        overlapDecisionRef.current !== 'direct' || presenceRef.current !== 'awake') return false;
    overlapDecisionRef.current = 'failed';
    // Abort privately, WITHOUT a reason. A reason calls the PCM error callback
    // and could convert this recoverable response failure back into OFFLINE.
    overlapGateRef.current?.abort();
    overlapGateRef.current = null;
    audioPlayingRef.current = false;
    if (!overlapDirectVerifiedRef.current) {
      if (overlapDirectTimerRef.current !== null) window.clearTimeout(overlapDirectTimerRef.current);
      overlapDirectTimerRef.current = null;
      setCaption('');
      setStateSafely('idle','Ready');
      sendControlMessage({kind:'desktop_overlap_audio',turn,phase:'unconfirmed_direct_discarded',
        reason:'unconfirmed_incomplete_response'});
      return true;
    }
    const partial = normalizeCaptionForDisplay(overlapReplyRef.current).trim();
    const note = 'I couldn’t finish that response. Ask me to continue or try again.';
    setCaption(partial ? `${partial}\n\n${note}` : note);
    setStateSafely('idle','Ready');
    sendControlMessage({kind:'desktop_overlap_audio',turn,phase:'recoverable_incomplete',
      reason,had_partial_transcript:Boolean(partial),completed_voice_delivered:false,
      partial_playback_possible:Boolean(latencyRef.current.firstAudio)});
    return true;
  };

  const fallbackCoreLunaVoice = (turn: number, reason: string) => {
    // A voice renderer failure does NOT mean Core/Luna failed or that the
    // desktop session went offline. Fail audio closed, but keep the verified
    // result readable and leave the same awake session available for retry.
    if (!coreLunaProbeRef.current || overlapCandidateStageRef.current !== 'core_luna_voice' ||
        turn !== overlapActiveTurnRef.current || presenceRef.current !== 'awake' ||
        overlapDecisionRef.current !== 'direct') return false;
    overlapDecisionRef.current = 'failed';
    overlapGateRef.current?.abort(); // a normal abort must not invoke the PCM error callback
    overlapGateRef.current = null;
    audioPlayingRef.current = false;
    const verifiedText = coreLunaVerifiedTextRef.current;
    setCaption(verifiedText || 'Core completed the request, but I could not play its answer.');
    setStateSafely('idle','Core result available as text; speech synthesis interrupted');
    sendControlMessage({kind:'desktop_luna_voice',turn,phase:'text_fallback',reason,
      core_text_chars:verifiedText.length,voice_delivered:false});
    return true;
  };

  const speakCoreLunaResult = (payload: {turn?: number; status?: string; text?: string; origin?: string}) => {
    const turn = Number(payload.turn || 0);
    if (!coreLunaProbeRef.current || turn <= 0 || turn !== overlapActiveTurnRef.current ||
        overlapDecisionRef.current !== 'tool' || presenceRef.current !== 'awake') return;
    const dc = dcRef.current;
    if (dc?.readyState !== 'open') return;
    const resultText = String(payload.text || '').trim().slice(0, 3000);
    if (!resultText) { setStateSafely('idle','Luna returned no usable result'); return; }
    coreLunaVerifiedTextRef.current = resultText;
    // Original candidate was cancelled and *never* authorized. Reuse the same
    // private PCM gate only for a NEW response owned by this exact turn.
    overlapGateRef.current?.abort();
    overlapGateRef.current = null;
    overlapCandidateStageRef.current = 'core_luna_voice';
    overlapCandidateIdRef.current = '';
    overlapCandidateDoneRef.current = false;
    overlapAudioStartedRef.current = false;
    overlapAudioDrainedRef.current = false;
    overlapReplyRef.current = '';
    overlapDecisionRef.current = 'direct';
    overlapDirectVerifiedRef.current = true; // Core text already authorized by the verified tool result.
    setCaption('');
    setStateSafely('thinking','Speaking Core result');
    const originalItem = overlapCommittedItemRef.current;
    const input: any[] = [];
    if (/^item_[A-Za-z0-9_-]+$/.test(originalItem)) input.push({type:'item_reference',id:originalItem});
    input.push({type:'message',role:'user',content:[{type:'input_text',
      text:`Jarvis Core returned this ${payload.origin === 'tool' ? 'verified browser-action outcome' : (payload.status === 'completed' ? 'verified reasoning answer' : 'verified failure')} for your most recent request. Speak this faithfully without new factual claims or actions:\n${resultText}`}]});
    dc.send(JSON.stringify({type:'response.create',response:{conversation:'none',
      metadata:{jarvis_stage:'core_luna_voice',jarvis_turn:String(turn)},
      // Audio tokens and transcript tokens share this limit. Unlike the short
      // speculative candidate, a bounded 3000-character Core answer must not
      // be truncated by a 1024-token voice-synthesis budget.
      input,output_modalities:['audio'],max_output_tokens:'inf',tools:[],tool_choice:'none',
      instructions:'You are Jarvis speaking an already obtained Core result. Give the answer naturally and faithfully, without claiming any additional research, external actions, or capabilities. Never announce internal routing or say that you are about to check something. If Core reported a failure, communicate that failure accurately. Do not run tools.'}}));
    sendControlMessage({kind:'desktop_luna_voice',turn,phase:'started',status:String(payload.status || '')});
  };

  // A model selecting test_action is only a proposal. Core receives the
  // independent matching typed/committed-audio transcript; never model arguments.
  const settlePendingOverlapAction = (timeout = false) => {
    const pending = overlapPendingActionRef.current;
    if (!pending) return;
    if (pending.epoch !== overlapEpochRef.current || pending.turn !== overlapActiveTurnRef.current ||
        presenceRef.current !== 'awake') {
      overlapPendingActionRef.current = null;
      if (overlapActionTimerRef.current !== null) window.clearTimeout(overlapActionTimerRef.current);
      overlapActionTimerRef.current = null;
      return;
    }
    const input = overlapSleepInputRef.current;
    if (!input || input.turn !== pending.turn || input.binding !== overlapInputBindingRef.current) {
      if (!timeout) return;
    }
    overlapPendingActionRef.current = null;
    if (overlapActionTimerRef.current !== null) window.clearTimeout(overlapActionTimerRef.current);
    overlapActionTimerRef.current = null;
    // The exact pending turn is now dispatched. Keep explicit result ownership
    // even if the browser Core responds before candidate-cancel telemetry ends.
    overlapAwaitingActionResultRef.current = {turn:pending.turn,epoch:pending.epoch};
    if (overlapActionResultTimerRef.current !== null) window.clearTimeout(overlapActionResultTimerRef.current);
    overlapActionResultTimerRef.current = window.setTimeout(() => {
      const awaiting = overlapAwaitingActionResultRef.current;
      if (!awaiting || awaiting.turn !== pending.turn || awaiting.epoch !== overlapEpochRef.current ||
          awaiting.turn !== overlapActiveTurnRef.current || presenceRef.current !== 'awake') return;
      overlapAwaitingActionResultRef.current = null;
      overlapActionResultTimerRef.current = null;
      overlapGateRef.current?.abort();
      overlapGateRef.current = null;
      overlapDecisionRef.current = 'failed';
      // The action MAY have succeeded even if its acknowledgment went missing.
      // Never automatically replay it or claim that nothing happened.
      setCaption('I could not confirm the browser result. Check the browser; I will not retry automatically.');
      setStateSafely('idle', 'Ready');
      sendControlMessage({kind:'desktop_action_feedback',turn:pending.turn,status:'unknown',
        visible_confirmation:false,spoken:false,reason:'result_timeout'});
    }, 5000);
    sendControlMessage({kind:'desktop_action_request',turn:pending.turn,selected_tool:'test_action',
      source:input?.turn === pending.turn && input?.binding === overlapInputBindingRef.current ? input.source : '',
      binding:input?.turn === pending.turn && input?.binding === overlapInputBindingRef.current ? input.binding : '',
      text:input?.turn === pending.turn && input?.binding === overlapInputBindingRef.current ? input.text : ''});
  };

  // An audio item is not proof that a user spoke actual words: semantic VAD
  // can commit a mic bump or audio feedback. Keep direct PCM private until the
  // SAME item receives a usable transcript. Typed requests are already confirmed.
  const settlePendingOverlapDirect = () => {
    if (!overlapProbeRef.current || overlapDecisionRef.current !== 'direct' ||
        overlapCandidateStageRef.current !== 'overlap_candidate' ||
        overlapDirectVerifiedRef.current || presenceRef.current !== 'awake') return;
    const input = overlapSleepInputRef.current;
    if (!input || input.turn !== overlapActiveTurnRef.current ||
        input.binding !== overlapInputBindingRef.current ||
        !hasSubstantiveUserWords(input.text)) return;
    overlapDirectVerifiedRef.current = true;
    if (overlapPerfRef.current.turn === input.turn) overlapPerfRef.current.gateAuthorized = performance.now();
    if (overlapDirectTimerRef.current !== null) window.clearTimeout(overlapDirectTimerRef.current);
    overlapDirectTimerRef.current = null;
    overlapGateRef.current?.authorize();
    sendControlMessage({kind:'desktop_overlap_audio',turn:input.turn,phase:'direct_input_confirmed',
      source:input.source,confirmed_chars:input.text.length});
    if (overlapCandidateDoneRef.current && overlapReplyRef.current) {
      setCaption(overlapReplyRef.current);
      sendControlMessage({kind:'desktop_reply',turn:input.turn,source:'overlap_realtime',text:overlapReplyRef.current});
    }
  };

  const rejectUnconfirmedDirect = (turn: number, epoch: number) => {
    if (epoch !== overlapEpochRef.current || turn !== overlapActiveTurnRef.current ||
        overlapDecisionRef.current !== 'direct' || overlapDirectVerifiedRef.current ||
        overlapCandidateStageRef.current !== 'overlap_candidate') return;
    overlapDirectTimerRef.current = null;
    overlapDecisionRef.current = 'failed';
    overlapGateRef.current?.abort();
    overlapGateRef.current = null;
    if (overlapCandidateIdRef.current && dcRef.current?.readyState === 'open') {
      dcRef.current.send(JSON.stringify({type:'response.cancel',response_id:overlapCandidateIdRef.current}));
      dcRef.current.send(JSON.stringify({type:'output_audio_buffer.clear'}));
    }
    sendControlMessage({kind:'desktop_overlap_audio',turn,phase:'unconfirmed_direct_discarded',
      reason:overlapSleepInputRef.current ? 'insufficient_speech_evidence' : 'transcript_timeout'});
    setStateSafely('idle','Ready');
  };

  // A tool decision may arrive before Realtime finishes transcribing the
  // committed item. Do not sleep or release private speech until evidence is
  // corroborated by that exact current-turn item. A timeout fails closed.
  const settlePendingOverlapSleep = (timeout = false) => {
    const pending = overlapPendingSleepRef.current;
    if (!pending) return;
    if (pending.turn !== overlapActiveTurnRef.current || pending.epoch !== overlapEpochRef.current ||
        presenceRef.current !== 'awake') {
      overlapPendingSleepRef.current = null;
      if (overlapSleepTimerRef.current !== null) window.clearTimeout(overlapSleepTimerRef.current);
      overlapSleepTimerRef.current = null;
      return;
    }
    const confirmed = overlapSleepInputRef.current;
    if (!confirmed && !timeout) return;
    const approved = isVerifiedSleepEvidence(pending.evidence,confirmed,pending.turn,
      overlapInputBindingRef.current,wakePhraseRef.current);
    sendControlMessage({kind:'desktop_overlap_audio',turn:pending.turn,phase:'sleep_evidence_check',
      evidence:pending.evidence.slice(0,160),confirmed_text:confirmed?.text?.slice(0,160) || '',
      source:confirmed?.source || 'missing',same_binding:confirmed?.binding === overlapInputBindingRef.current,
      approved});
    overlapPendingSleepRef.current = null;
    if (overlapSleepTimerRef.current !== null) window.clearTimeout(overlapSleepTimerRef.current);
    overlapSleepTimerRef.current = null;
    if (approved) {
      sendControlMessage({kind:'desktop_overlap_audio',turn:pending.turn,phase:'sleep',
        decision_ms:overlapDecisionMsRef.current,reason:'verified_user_sleep_request'});
      void enterSleep('voice_command');
    } else {
      overlapDecisionRef.current = 'failed'; // Late candidate cancellation is not a fatal error.
      sendControlMessage({kind:'desktop_overlap_audio',turn:pending.turn,phase:'sleep_rejected',
        reason:timeout && !confirmed ? 'sleep_transcript_timeout' : 'sleep_evidence_mismatch'});
      setCaption('I could not confirm the sleep request.');
      setStateSafely('idle','Ready');
    }
  };

  const handleRealtimeEvent = (event: RealtimeEvent) => {
    const type = event.type || '';
    const now = performance.now();
    // VAD speech_stopped may precede committed audio-item creation. Never run
    // either parallel model on an implicit 'latest' context during that window.
    if (overlapProbeRef.current && type === 'input_audio_buffer.committed') {
      const itemId = String(event.item_id || '');
      if (itemId) {
        overlapCommittedItemRef.current = itemId;
        if (overlapAwaitingCommitRef.current) requestOverlapResponses(dcRef.current, itemId);
      } else if (overlapAwaitingCommitRef.current) {
        sendControlMessage({kind:'desktop_overlap_audio',turn:latencyRef.current.turn,phase:'error',reason:'commit_missing_item_id'});
        overlapAwaitingCommitRef.current = false;
        setStateSafely('error','Speech input commit missing ID');
      }
      return;
    }
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
      if (overlapProbeRef.current && itemId && transcript) {
        overlapTranscriptsRef.current.set(itemId,transcript);
        while (overlapTranscriptsRef.current.size > 64) {
          overlapTranscriptsRef.current.delete(overlapTranscriptsRef.current.keys().next().value || '');
        }
        // Item identity is stronger than event ordering or inferred turn number.
        if (itemId === overlapInputBindingRef.current && overlapActiveTurnRef.current > 0) {
          overlapSleepInputRef.current = {turn:overlapActiveTurnRef.current,
            binding:itemId,source:'voice',text:transcript};
          if (overlapPerfRef.current.turn === overlapActiveTurnRef.current)
            overlapPerfRef.current.transcript = now;
          settlePendingOverlapSleep();
          settlePendingOverlapDirect();
          settlePendingOverlapAction();
        }
      }
      if (conversationTraceRef.current && transcript) {
        sendControlMessage({
          kind: 'desktop_user',
          turn,
          source: 'voice',
          text: transcript,
          transcript_ms: latencyRef.current.speechStopped === undefined ? null : Math.round(now - latencyRef.current.speechStopped),
        });
      }
      if (itemId) userItemTurnsRef.current.delete(itemId);
    }
    // Experimental parallel text authority + continuous PRIVATE WebRTC audio.
    // The actual provider track remains muted for the WHOLE session. Only the
    // AudioWorklet PCM gate alone can produce authorized speech, never pre-tool audio.
    if (overlapProbeRef.current && type !== 'input_audio_buffer.speech_started' && type !== 'input_audio_buffer.speech_stopped') {
      if (audioRef.current) audioRef.current.muted = true;
      const responseId = String(event.response?.id || event.response_id || '');
      const stage = String(event.response?.metadata?.jarvis_stage || '');
      const turn = latencyRef.current.turn;
      if (type === 'response.created') {
        // Response events from a cancelled older turn must never claim ownership.
        if (Number(event.response?.metadata?.jarvis_turn || 0) !== overlapActiveTurnRef.current || !overlapActiveTurnRef.current) return;
        if (stage === 'overlap_decision') overlapDecisionIdRef.current = responseId;
        if (stage === overlapCandidateStageRef.current) {
          if (overlapPerfRef.current.turn === turn) overlapPerfRef.current.candidate = now;
          overlapCandidateIdRef.current = responseId;
          const stream = bufferedRemoteStreamRef.current;
          const epoch = overlapEpochRef.current;
          if (!stream) {
            sendControlMessage({kind:'desktop_overlap_audio',turn,phase:'error',reason:'remote_stream_unavailable'});
            if (!fallbackCoreLunaVoice(turn,'remote_stream_unavailable') &&
                !recoverIncompleteDirectResponse(turn,'remote_stream_unavailable')) {
              overlapDecisionRef.current = 'failed';
              setStateSafely('error','Private audio stream unavailable');
            }
          } else try {
            void StreamingPcmGate.create(stream, () => {
              if (epoch !== overlapEpochRef.current || overlapDecisionRef.current !== 'direct') return;
              latencyRef.current.firstAudio ??= performance.now();
              if (!latencyRef.current.reported) {latencyRef.current.reported=true;sendLatencySummary();}
              const p = overlapPerfRef.current;
              if (p.turn === turn && latencyRef.current.speechStopped !== undefined) {
                const start = latencyRef.current.speechStopped;
                const ms = (t:number|null) => t === null ? null : Math.round(t-start);
                sendControlMessage({kind:'desktop_overlap_audio',turn,phase:'latency_breakdown',
                  commit_ms:ms(p.commit),transcript_ms:ms(p.transcript),route_ms:ms(p.route),
                  candidate_created_ms:ms(p.candidate),pcm_ready_ms:ms(p.pcmReady),
                  gate_authorized_ms:ms(p.gateAuthorized),first_audio_ms:Math.round(performance.now()-start),
                  pcm_signal_ms:ms(p.pcmSignal),pcm_buffer_ready_ms:ms(p.pcmBufferReady),
                  signal_to_first_audio_ms:p.pcmSignal === null ? null : Math.round(performance.now()-p.pcmSignal),
                  authorized_to_first_audio_ms:p.gateAuthorized === null ? null : Math.round(performance.now()-p.gateAuthorized),
                  pcm_trim_enabled:pcmTrimRef.current,
                  model_route_before_transcript:p.route!==null&&p.transcript!==null&&p.route<p.transcript});
              }
              setStateSafely('speaking','Speaking');
              audioPlayingRef.current = true;
              sendControlMessage({kind:'desktop_overlap_audio',turn,phase:'released',
                decision_ms:overlapDecisionMsRef.current,
                first_playback_ms:latencyRef.current.speechStopped===undefined?null:Math.round(performance.now()-latencyRef.current.speechStopped)});
            }, () => {
              if (epoch !== overlapEpochRef.current) return;
              overlapGateRef.current?.abort();
              overlapGateRef.current = null;
              audioPlayingRef.current = false;
              scheduleIdle(120);
            }, (reason) => {
              if (epoch !== overlapEpochRef.current) return;
              sendControlMessage({kind:'desktop_overlap_audio',turn,phase:'error',reason});
              if (!fallbackCoreLunaVoice(turn,'pcm_'+reason) &&
                  !recoverIncompleteDirectResponse(turn,'pcm_'+reason) && overlapDecisionRef.current !== 'failed')
                setStateSafely('error','Streaming audio failed: '+reason);
            }, (count) => {
              // Previously missing argument: avoid throwing from the AudioWorklet
              // on legitimate network/synthesis underflow diagnostics.
              if (epoch === overlapEpochRef.current && count === 1)
                sendControlMessage({kind:'desktop_overlap_audio',turn,phase:'pcm_underflow',reason:'first_underflow'});
            }, pcmTrimRef.current, (stage) => {
              // Deliberately no transcript or private audio in timing events.
              if (epoch !== overlapEpochRef.current || overlapPerfRef.current.turn !== turn) return;
              const p = overlapPerfRef.current;
              if (stage === 'first_pcm_signal' && p.pcmSignal === null) p.pcmSignal = performance.now();
              if (stage === 'pcm_buffer_ready' && p.pcmBufferReady === null) p.pcmBufferReady = performance.now();
            }).then((gate) => {
              if (epoch !== overlapEpochRef.current || overlapDecisionRef.current === 'tool' || overlapDecisionRef.current === 'failed') {
                gate.abort();
                return;
              }
              overlapGateRef.current = gate;
              if (overlapPerfRef.current.turn === turn) overlapPerfRef.current.pcmReady = performance.now();
              if (overlapDecisionRef.current === 'direct' && overlapDirectVerifiedRef.current) gate.authorize();
              if (overlapCandidateDoneRef.current && overlapAudioDrainedRef.current) gate.finish();
            }).catch((error) => {
              if (epoch !== overlapEpochRef.current) return;
              sendControlMessage({kind:'desktop_overlap_audio',turn,phase:'error',reason:String(error)});
              if (!fallbackCoreLunaVoice(turn,'pcm_unavailable') &&
                  !recoverIncompleteDirectResponse(turn,'pcm_unavailable') &&
                  !(overlapCandidateStageRef.current === 'core_luna_voice' && overlapDecisionRef.current === 'failed')) {
                overlapDecisionRef.current = 'failed';
                setStateSafely('error','Private PCM audio unavailable');
              }
            });
          } catch (error) {
            sendControlMessage({kind:'desktop_overlap_audio',turn,phase:'error',reason:String(error)});
            if (!fallbackCoreLunaVoice(turn,'pcm_unavailable') &&
                !recoverIncompleteDirectResponse(turn,'pcm_unavailable') &&
                !(overlapCandidateStageRef.current === 'core_luna_voice' && overlapDecisionRef.current === 'failed')) {
                overlapDecisionRef.current = 'failed';
                setStateSafely('error','Private PCM audio unavailable');
              }
          }
        }
        return;
      }
      if (type === 'output_audio_buffer.started') {
        if (overlapCandidateIdRef.current) overlapAudioStartedRef.current = true;
        return;
      }
      if (type === 'response.output_audio_transcript.delta' && responseId === overlapCandidateIdRef.current) {
        overlapReplyRef.current += String(event.delta || '');
        if (overlapReplyRef.current.length > 20000) overlapReplyRef.current = overlapReplyRef.current.slice(0, 20000);
        if (overlapDecisionRef.current === 'direct' && overlapDirectVerifiedRef.current && overlapCandidateStageRef.current !== 'core_luna_voice')
          setCaption(overlapReplyRef.current);
        return;
      }
      if (type === 'response.done') {
        sendControlMessage({kind:'realtime_event',event}); // Billing only. Never dispatch tools in this probe.
        if (Number(event.response?.metadata?.jarvis_turn || 0) !== overlapActiveTurnRef.current || !overlapActiveTurnRef.current) return;
        if (responseId === overlapDecisionIdRef.current && stage === 'overlap_decision') {
          overlapDecisionMsRef.current = Math.round(performance.now()-overlapStartedRef.current);
          if (overlapPerfRef.current.turn === turn) overlapPerfRef.current.route = performance.now();
          latencyRef.current.routeDecided = performance.now();
          const completed = event.response?.status === 'completed';
          const calls = (event.response?.output || []).filter(item => item?.type === 'function_call');
          if (!completed) overlapDecisionRef.current = 'failed';
          else overlapDecisionRef.current = calls.length ? 'tool' : 'direct';
          const tool = calls.length ? String(calls[0].name || 'unknown') : 'none';
          // The local sleep lifecycle is not a dry-run tool. Evidence is required
          // to prevent a bare tool label from terminating a conversation.
          if (tool === 'sleep_jarvis') {
            let evidence = '';
            try { evidence = String(JSON.parse(calls[0].arguments || '{}').sleep_evidence || '').trim(); } catch (_) { /* fail closed */ }
            // A tool label is not authorization. Abort unapproved private PCM,
            // including if the model decision beat its STT transcription.
            overlapGateRef.current?.abort();
            overlapGateRef.current = null;
            if (overlapCandidateIdRef.current && dcRef.current?.readyState === 'open') {
              dcRef.current.send(JSON.stringify({type:'response.cancel',response_id:overlapCandidateIdRef.current}));
              dcRef.current.send(JSON.stringify({type:'output_audio_buffer.clear'}));
            }
            if (completed && calls.length === 1 && evidence.length > 0 && evidence.length <= 160) {
              overlapPendingSleepRef.current = {turn,epoch:overlapEpochRef.current,evidence};
              sendControlMessage({kind:'desktop_overlap_audio',turn,phase:'sleep_pending_confirmation',
                reason:overlapSleepInputRef.current ? 'input_available' : 'awaiting_transcript'});
              if (overlapSleepInputRef.current) settlePendingOverlapSleep();
              else overlapSleepTimerRef.current = window.setTimeout(() => settlePendingOverlapSleep(true),2500);
            } else {
              overlapDecisionRef.current = 'failed';
              setCaption('I could not confirm the sleep request.');
              sendControlMessage({kind:'desktop_overlap_audio',turn,phase:'sleep_rejected',reason:'missing_or_invalid_sleep_evidence'});
              setStateSafely('idle','Ready');
            }
            return;
          }
          const realLuna = coreLunaProbeRef.current && completed && calls.length === 1 && tool === 'ask_luna';
          sendControlMessage({kind:'desktop_tool_probe',turn,tool,phase:'selection',dry_run:!realLuna,executed:false,
            decision_ms:overlapDecisionMsRef.current});
          sendControlMessage({kind:'desktop_overlap_audio',turn,phase:overlapDecisionRef.current,decision_ms:overlapDecisionMsRef.current});
          if (overlapDecisionRef.current === 'direct') {
            settlePendingOverlapDirect();
            if (!overlapDirectVerifiedRef.current) {
              const epoch = overlapEpochRef.current;
              overlapDirectTimerRef.current = window.setTimeout(() => rejectUnconfirmedDirect(turn,epoch),2500);
              sendControlMessage({kind:'desktop_overlap_audio',turn,phase:'direct_pending_transcription'});
            }
            if (overlapDirectVerifiedRef.current && overlapReplyRef.current) setCaption(overlapReplyRef.current);
            if (overlapDirectVerifiedRef.current && overlapCandidateDoneRef.current) {
              sendControlMessage({kind:'desktop_reply',turn,source:'overlap_realtime',text:overlapReplyRef.current});
            }
          } else {
            overlapGateRef.current?.abort();
            overlapGateRef.current = null;
            if (overlapCandidateIdRef.current && dcRef.current?.readyState === 'open') {
              dcRef.current.send(JSON.stringify({type:'response.cancel',response_id:overlapCandidateIdRef.current}));
              dcRef.current.send(JSON.stringify({type:'output_audio_buffer.clear'}));
            }
            if (coreActionsProbeRef.current && completed && calls.length === 1 && tool === 'test_action') {
              overlapPendingActionRef.current = {turn,epoch:overlapEpochRef.current};
              setStateSafely('working','Validating browser action');
              settlePendingOverlapAction();
              if (overlapPendingActionRef.current) {
                const epoch = overlapEpochRef.current;
                overlapActionTimerRef.current = window.setTimeout(() => {
                  if (overlapEpochRef.current === epoch) settlePendingOverlapAction(true);
                }, 2500);
              }
            } else if (realLuna) {
              // Core will separately return the only approved turn's result.
              // No speculative audio or misleading success is released here.
              setStateSafely('working','Core reasoning');
            } else {
              const message = overlapDecisionRef.current === 'tool'
                ? `${tool} was selected, but this is a dry-run. No tool or action was executed.`
                : 'I could not verify which system should answer. Nothing was executed.';
              setCaption(message);
              sendControlMessage({kind:'desktop_reply',turn,source:'overlap_safe_text',text:message});
              setStateSafely('idle','Ready');
            }
          }
          return;
        }
        if (responseId === overlapCandidateIdRef.current && stage === overlapCandidateStageRef.current) {
          overlapCandidateDoneRef.current = true;
          if (event.response?.status !== 'completed') {
            if (overlapDecisionRef.current === 'direct') {
              const reason = String(event.response?.status_details?.reason || event.response?.status || 'incomplete');
              if (!fallbackCoreLunaVoice(turn,reason)) {
                if (!recoverIncompleteDirectResponse(turn,reason)) {
                  overlapGateRef.current?.abort();
                  overlapGateRef.current = null;
                  // Stale or superseded responses do not affect the current UI.
                }
              }
            }
          } else {
            overlapReplyRef.current = overlapReplyRef.current.trim() || responseTranscript(event.response);
            if (overlapDecisionRef.current === 'direct' && overlapDirectVerifiedRef.current) {
              setCaption(overlapReplyRef.current);
              sendControlMessage({kind:'desktop_reply',turn,source:'overlap_realtime',text:overlapReplyRef.current});
              if (overlapCandidateStageRef.current === 'core_luna_voice')
                sendControlMessage({kind:'desktop_luna_voice',turn,phase:'synthesis_completed',status:'completed'});
            }
            if (overlapAudioDrainedRef.current) overlapGateRef.current?.finish();
          }
          return;
        }
        return;
      }
      if (type === 'output_audio_buffer.stopped' || type === 'output_audio_buffer.cleared') {
        if (!overlapAudioStartedRef.current) return;
        overlapAudioDrainedRef.current = true;
        if (overlapCandidateDoneRef.current) overlapGateRef.current?.finish();
        return;
      }
      if (type === 'error') {
        // A cancelled private candidate may report an error after a sleep
        // tool was chosen. It must not convert a safely pending/rejected sleep
        // (or an already-sleeping session) into OFFLINE.
        if (overlapPendingSleepRef.current || !overlapActiveTurnRef.current ||
            presenceRef.current !== 'awake' || overlapDecisionRef.current === 'failed') {
          sendControlMessage({kind:'desktop_overlap_audio',turn,phase:'cancellation_error_ignored',
            reason:String(event.error?.code || event.error?.message || 'provider_error')});
          return;
        }
        const reason = String(event.error?.code || event.error?.message || 'provider_error');
        if (!fallbackCoreLunaVoice(turn,reason) && !recoverIncompleteDirectResponse(turn,reason)) {
          // A decision-stage or transport error is distinct from an incomplete
          // authorized direct reply and still requires explicit investigation.
          overlapGateRef.current?.abort();
          overlapGateRef.current = null;
          if (overlapDecisionRef.current !== 'failed')
            setStateSafely('error',event.error?.message || 'Parallel probe error');
        }
      }
      return;
    }
    // Experimental audio publication gate. The remote WebRTC HTMLAudioElement
    // stays muted throughout this mode. MediaRecorder holds audio privately until
    // the model's COMPLETE response proves no tool was called. On a tool call,
    // every pre-tool syllable is discarded; only the simulated post-tool result
    // can become audible. This deliberately trades direct latency for safety.
    if (bufferedToolProbeRef.current && type !== 'input_audio_buffer.speech_started' && type !== 'input_audio_buffer.speech_stopped') {
      const responseId = String(event.response?.id || event.response_id || '');
      if (type === 'response.created') {
        if (bufferedCaptureRef.current) discardBufferedCapture();
        beginBufferedCapture(responseId);
        setStateSafely('thinking', 'Waiting for safe audio decision');
        return;
      }
      if (responseId && responseId !== bufferedResponseIdRef.current) return;
      if (type === 'response.output_audio_transcript.delta') {
        bufferedReplyRef.current += String(event.delta || '');
        if (bufferedReplyRef.current.length > 20000) bufferedReplyRef.current = bufferedReplyRef.current.slice(0,20000);
        return;
      }
      if (type === 'output_audio_buffer.started') {
        bufferedAudioSeenRef.current = true;
        bufferedAudioStartedRef.current ||= performance.now();
        return;
      }
      if (type === 'response.done') {
        sendControlMessage({kind:'realtime_event',event}); // Billing only; no bridge execution in this mode.
        if (event.response?.status !== 'completed' || bufferedOutcomeRef.current === 'blocked') {
          const status = String(event.response?.status || 'unknown');
          const isFollowup = bufferedWasFollowupRef.current;
          bufferedOutcomeRef.current = 'blocked';
          discardBufferedCapture();
          sendControlMessage({kind:'desktop_buffered_audio',turn:latencyRef.current.turn,phase:'discarded',reason:'response_incomplete_or_capture_unavailable',status});
          // Fail closed: truncated audio is NEVER played. But don't strand the
          // UI in Thinking. This text only reports a verified dry-run failure.
          if (isFollowup) {
            const safe = 'I couldn’t finish that simulated reply. No action or Luna call was executed.';
            setCaption(safe);
            sendControlMessage({kind:'desktop_reply',turn:latencyRef.current.turn,source:'simulated_tool_failure',text:safe});
          }
          setStateSafely('idle', 'Ready');
          scheduleIdle(160);
          return;
        }
        const calls = (event.response?.output || []).filter(item => item?.type === 'function_call');
        if (calls.length) {
          bufferedOutcomeRef.current = 'tool';
          bufferedPendingToolRef.current = calls;
          discardBufferedCapture();
          sendControlMessage({kind:'desktop_buffered_audio',turn:latencyRef.current.turn,phase:'discarded',selected:'tool',reason:'pretool_audio_not_authorized'});
          // Wait for the provider output buffer to drain/clear so no tool preamble
          // can be intermixed with the next post-tool voice recording.
          if (!bufferedAudioSeenRef.current || bufferedOutputDrainedRef.current) launchBufferedFollowup();
        } else {
          bufferedOutcomeRef.current = 'approved';
          bufferedReplyRef.current = bufferedReplyRef.current.trim() || responseTranscript(event.response);
          if (bufferedAudioSeenRef.current) finalizeBufferedIfReady();
          if (!bufferedAudioSeenRef.current) {
            // Provider returned a text-only response despite audio mode. Safe to
            // display the confirmed result, but never claim speech happened.
            discardBufferedCapture();
            setCaption(bufferedReplyRef.current);
            sendControlMessage({kind:'desktop_reply',turn:latencyRef.current.turn,source:'realtime_text_fallback',text:bufferedReplyRef.current});
            scheduleIdle(130);
          }
        }
        return;
      }
      if (type === 'output_audio_buffer.stopped' || type === 'output_audio_buffer.cleared') {
        bufferedOutputDrainedRef.current = true;
        // No decision yet? Preserve the private recording until response.done.
        // There is no authority to discard or play it at this point.
        finalizeBufferedIfReady();
        return;
      }
      if (type === 'error') {
        discardBufferedCapture();
        bufferedOutcomeRef.current = 'blocked';
        setStateSafely('error',event.error?.message || 'Buffered audio failed');
      }
      return;
    }
    // Probe-specific interception must NEVER swallow VAD lifecycle events.
    // Shared speech_started increments the turn, and speech_stopped schedules
    // the one text-only response. Previously both were discarded here, leaving
    // a valid STT transcript with turn=n/a and no response.create at all.
    if (toolProbeRef.current && type !== 'input_audio_buffer.speech_started' && type !== 'input_audio_buffer.speech_stopped') {
      // The response is always text-only. No audio can escape before a tool call.
      // Tool results are deterministic simulations, never real Core/Luna actions.
      if (type === 'response.output_text.delta') {
        toolProbeTextRef.current += String(event.delta || '');
        if (toolProbeTextRef.current.length > 30000) toolProbeTextRef.current = toolProbeTextRef.current.slice(0, 30000);
        return;
      }
      if (type === 'response.output_audio.delta' || type === 'output_audio_buffer.started') {
        // Defense-in-depth if provider violates output_modalities=['text'].
        if (audioRef.current) audioRef.current.muted = true;
        if (dcRef.current?.readyState === 'open') dcRef.current.send(JSON.stringify({ type: 'output_audio_buffer.clear' }));
        sendControlMessage({ kind:'desktop_tool_probe', turn:latencyRef.current.turn, tool:'unexpected_audio', phase:'blocked' });
        return;
      }
      if (type === 'response.done') {
        // A cancelled/interrupted speculative tool call has no authority to post even a simulation.
        if (event.response?.status !== 'completed') {
          toolProbeTextRef.current = '';
          return;
        }
        const outputs = event.response?.output || [];
        const calls = outputs.filter((item) => item?.type === 'function_call');
        const turn = latencyRef.current.turn || turnCounterRef.current;
        if (calls.length) {
          const pretool = toolProbeTextRef.current.length;
          for (const call of calls) {
            const name = String(call.name || 'unknown');
            const cid = String(call.call_id || '');
            const allowed = name === 'ask_luna' || name === 'test_action';
            sendControlMessage({ kind:'desktop_tool_probe', turn, tool:name, phase:'selection', pretool_text_chars:pretool, decision_ms:latencyRef.current.speechStopped === undefined ? null : Math.round(performance.now()-latencyRef.current.speechStopped) });
            const result = !allowed
              ? { status:'blocked', executed:false, message:'This tool is not allowed in the dry-run.' }
              : name === 'ask_luna'
                ? { status:'not_executed', executed:false, message:'Luna was selected, but this dry-run did not call Luna.' }
                : { status:'unavailable', executed:false, message:'This simulated action did not start any real work.' };
            if (cid && dcRef.current?.readyState === 'open') {
              dcRef.current.send(JSON.stringify({ type:'conversation.item.create', item:{ type:'function_call_output',call_id:cid,output:JSON.stringify(result) } }));
            }
          }
          toolProbeTextRef.current = '';
          if (dcRef.current?.readyState === 'open') {
            dcRef.current.send(JSON.stringify({type:'response.create',response:{max_output_tokens:256,output_modalities:['text'],tools:[],tool_choice:'none',instructions:'Give one concise truthful text-only summary of the simulated result. Do not claim Luna or actions actually ran.',metadata:{jarvis_stage:'tool_probe_followup',jarvis_turn:String(turn)}}}));
          }
        } else if (String(event.response?.status) === 'completed') {
          sendControlMessage({ kind:'desktop_tool_probe', turn, tool:'none', phase:'direct', pretool_text_chars:0, decision_ms:latencyRef.current.speechStopped === undefined ? null : Math.round(performance.now()-latencyRef.current.speechStopped) });
          const answer = (toolProbeTextRef.current || responseTranscript(event.response)).trim();
          if (answer) {
            setCaption(answer);
            sendControlMessage({ kind:'desktop_reply', turn, source:'tool_probe_text_only', text:answer });
          }
          toolProbeTextRef.current = '';
          scheduleIdle(150);
        } else {
          toolProbeTextRef.current = '';
        }
        return;
      }
      if (type === 'response.created') {
        toolProbeTextRef.current = '';
        setStateSafely('thinking', 'Text-only tool selection');
        return;
      }
      if (type === 'error') setStateSafely('error', event.error?.message || 'Tool probe error');
      return;
    }
    if (type === 'response.function_call_arguments.done' && event.name === 'route_jarvis_turn') {
      try {
        const routed = JSON.parse(String(event.arguments || '{}'));
        const route = String(routed?.route || 'unknown');
        latencyRef.current.routeDecided ??= now;
        latencyRef.current.route = route;
        cancelParallelShadows(latencyRef.current.turn);
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
    // Out-of-band shadow events are never allowed to change captions, routing,
    // current response ID, audio playback, memory, or turn lifecycle.
    if (type === 'response.created' && event.response?.metadata?.jarvis_stage === 'parallel_shadow') {
      const id = String(event.response?.id || '');
      const turn = Number(event.response?.metadata?.jarvis_turn || 0);
      if (id) {
        parallelShadowIdsRef.current.set(id, { turn, started: parallelShadowRequestedRef.current.get(turn) ?? now });
        if (parallelShadowPendingCancelRef.current.has(turn) && dcRef.current?.readyState === 'open') {
          dcRef.current.send(JSON.stringify({ type: 'response.cancel', response_id: id }));
        }
      }
      return;
    }
    const shadowId = String(event.response_id || event.response?.id || '');
    if (shadowId && parallelShadowIdsRef.current.has(shadowId)) {
      if (type === 'response.output_text.delta') {
        const candidate = parallelShadowIdsRef.current.get(shadowId)!;
        candidate.firstToken ??= now;
      }
      if (type === 'response.done') {
        const candidate = parallelShadowIdsRef.current.get(shadowId)!;
        const usage = event.response?.usage || {};
        sendControlMessage({
          kind: 'desktop_parallel_realtime', turn: candidate.turn,
          status: event.response?.status || 'unknown',
          elapsed_ms: Math.round(now - candidate.started),
          first_token_ms: candidate.firstToken === undefined ? null : Math.round(candidate.firstToken - candidate.started),
          text_tokens: usage?.output_token_details?.text_tokens ?? null,
          audio_tokens: usage?.output_token_details?.audio_tokens ?? null,
        });
        parallelShadowIdsRef.current.delete(shadowId);
        parallelShadowRequestedRef.current.delete(candidate.turn);
        parallelShadowPendingCancelRef.current.delete(candidate.turn);
      }
      return;
    }
    // Route telemetry is intentionally sent first so Core can bind this call_id
    // to the visible turn before the matching function-call event starts work.
    forwardToCore(event);
    if (type === 'input_audio_buffer.speech_started') {
      if (bufferedToolProbeRef.current) resetBufferedTurn();
      if (overlapProbeRef.current) cancelOverlap();
      clearIdleTimer();
      turnCounterRef.current += 1;
      latencyRef.current = { turn: turnCounterRef.current, speechStarted: now };
      setStateSafely('listening', 'I’m listening');
    } else if (type === 'input_audio_buffer.speech_stopped') {
      latencyRef.current.speechStopped = now;
      setStateSafely('thinking', 'Thinking');
      // Keep Semantic VAD for natural endpointing, but Jarvis owns response
      // creation so Core can attach a turn-specific compact response policy.
      if (toolProbeRef.current) {
        latencyRef.current.route = 'tool_probe';
        latencyRef.current.routeDecided = now;
      } else if (bufferedToolProbeRef.current) {
        latencyRef.current.route = 'buffered_tool_probe';
        latencyRef.current.routeDecided = now;
      }
      if (directOnlyBenchmarkRef.current) {
        latencyRef.current.route = 'direct_no_gate';
        latencyRef.current.routeDecided = now;
        sendControlMessage({ kind: 'desktop_fast_direct', turn: latencyRef.current.turn });
      }
      if (overlapProbeRef.current) awaitOverlapAudioCommit();
      else requestNormalRealtimeResponse();
      if (overlapProbeRef.current || toolProbeRef.current || bufferedToolProbeRef.current) { /* Neither probe spawns shadows. */ }
      else if (!directOnlyBenchmarkRef.current) requestParallelShadow();
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
              source: ['direct', 'direct_no_gate'].includes(String(latencyRef.current.route || '')) ? 'realtime' : 'core',
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
      if (preservedCommand) {
        if (reason === 'typed_wake') dispatchTextToRealtime(preservedCommand, 'typed');
        else dispatchTextToRealtime(preservedCommand);
      }
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
          parallelShadowEnabledRef.current = payload.parallel_shadow_probe === true;
          directOnlyBenchmarkRef.current = payload.direct_only_benchmark === true;
          toolProbeRef.current = payload.tool_selection_probe === true;
          bufferedToolProbeRef.current = payload.buffered_tool_probe === true;
          overlapProbeRef.current = payload.overlap_probe === true;
          coreLunaProbeRef.current = payload.core_luna_probe === true;
          coreActionsProbeRef.current = payload.core_actions_probe === true && coreLunaProbeRef.current && overlapProbeRef.current;
          delegationGuidanceRef.current = payload.delegation_guidance_probe === true && coreLunaProbeRef.current && overlapProbeRef.current;
          pcmTrimRef.current = payload.pcm_trim_leading_silence === true;
        } else if (payload.kind === 'core_luna_cancel_hold') {
          // Cancellation-test mode only. Never voices the held Core result.
          const heldTurn = Number(payload.turn);
          if (Number.isSafeInteger(heldTurn) && heldTurn > 0) {
            setCancelHoldTurn(heldTurn);
            cancelHoldTurnRef.current = heldTurn;
            // Windows host plays a native WAV through the default output;
            // do not start another browser AudioContext from this WS handler.
            if (payload.cue_route !== 'native_windows' && payload.cue_route !== 'silent') {
              void playLunaHoldCue().then((audible) => {
                sendControlMessage({kind:'desktop_luna_cancel_cue',turn:heldTurn,audible});
              });
            }
          }
        } else if (payload.kind === 'core_luna_cancel_cue_fallback') {
          const heldTurn = Number(payload.turn);
          if (heldTurn > 0 && heldTurn === cancelHoldTurnRef.current) {
            void playLunaHoldCue().then((audible) => {
              sendControlMessage({kind:'desktop_luna_cancel_cue',turn:heldTurn,audible});
            });
          }
        } else if (payload.kind === 'core_luna_cancel_hold_ended') {
          if (cancelHoldTurnRef.current === Number(payload.turn)) cancelHoldTurnRef.current = null;
          setCancelHoldTurn(current => current === Number(payload.turn) ? null : current);
        } else if (payload.kind === 'core_tool_result') {
          // An approved browser launch is visible confirmation in itself.
          // Settle the same-turn tool selection without asking Mini to speak,
          // and never leave the orb in WORKING after a denied capability.
          const turn = Number(payload.turn || 0);
          const awaiting = overlapAwaitingActionResultRef.current;
          if (coreActionsProbeRef.current && awaiting && turn > 0 &&
              awaiting.turn === turn && awaiting.epoch === overlapEpochRef.current &&
              turn === overlapActiveTurnRef.current && presenceRef.current === 'awake') {
            overlapAwaitingActionResultRef.current = null;
            if (overlapActionResultTimerRef.current !== null) window.clearTimeout(overlapActionResultTimerRef.current);
            overlapActionResultTimerRef.current = null;
            overlapPendingActionRef.current = null;
            if (overlapActionTimerRef.current !== null) window.clearTimeout(overlapActionTimerRef.current);
            overlapActionTimerRef.current = null;
            overlapGateRef.current?.abort();
            overlapGateRef.current = null;
            overlapDecisionRef.current = 'failed'; // Fail closed for late candidate audio.
            const completed = payload.status === 'completed';
            setCaption(completed ? '' : String(payload.text || 'I could not complete that action.'));
            setStateSafely('idle', 'Ready');
            // Some delayed cancelled-candidate events may arrive immediately
            // after Core's WS result. Reassert Ready without touching a new turn.
            window.setTimeout(() => {
              if (awaiting.epoch === overlapEpochRef.current &&
                  awaiting.turn === overlapActiveTurnRef.current &&
                  overlapDecisionRef.current === 'failed' && presenceRef.current === 'awake') {
                setStateSafely('idle', 'Ready');
              }
            }, 180);
            noteActivity();
            sendControlMessage({kind:'desktop_action_feedback',turn,status:completed ? 'completed' : 'failed',
              visible_confirmation:completed,spoken:false});
          }
        } else if (payload.kind === 'core_luna_result') {
          cancelHoldTurnRef.current = null;
          setCancelHoldTurn(null);
          speakCoreLunaResult(payload);
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
        bufferedRemoteStreamRef.current = remote;
        if (overlapProbeRef.current) {
          // Preload the SILENT worklet before the user asks a question. This
          // never attaches the remote stream or authorizes any audio.
          void StreamingPcmGate.prewarm().then(() => {
            sendControlMessage({kind:'desktop_overlap_audio',phase:'pcm_prewarm_ready'});
          }).catch(error => {
            sendControlMessage({kind:'desktop_overlap_audio',phase:'pcm_prewarm_failed',reason:String(error)});
          });
        }
        if (audioRef.current) {
          // Probe mode is unconditionally text-only, even before a response ID exists.
          audioRef.current.muted = true; // Fail closed until an authorized normal response explicitly unmutes.
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
        // Distinguish user-typed wake from a command preserved by local STT.
        if (reason === 'typed_wake') dispatchTextToRealtime(preservedCommand, 'typed');
        else dispatchTextToRealtime(preservedCommand, 'wake_transcript', reason === 'wake_only');
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
        {cancelHoldTurn !== null ? (
          <div className="luna-cancel-test-cue" role="status">TEST MODE · INTERRUPT NOW (8 SEC)</div>
        ) : null}
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
