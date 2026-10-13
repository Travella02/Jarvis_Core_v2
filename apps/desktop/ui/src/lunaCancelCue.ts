/** Short, local test-only notification for the private Core result hold.
 * Does not touch the live WebRTC output or PCM gate.
 */
export async function playLunaHoldCue(): Promise<boolean> {
  let context: AudioContext | null = null;
  try {
    context = new AudioContext();
    await context.resume();
    if (context.state !== 'running') {
      void context.close();
      return false;
    }
    const start = context.currentTime + 0.015;
    for (const [offset, frequency] of [[0, 880], [0.16, 1175]] as const) {
      const osc = context.createOscillator();
      const gain = context.createGain();
      osc.type = 'sine';
      osc.frequency.value = frequency;
      gain.gain.setValueAtTime(0.0001, start + offset);
      gain.gain.exponentialRampToValueAtTime(0.07, start + offset + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + offset + 0.135);
      osc.connect(gain);
      gain.connect(context.destination);
      osc.start(start + offset);
      osc.stop(start + offset + 0.14);
    }
    // Closing after the two short notes releases the audio device.
    const instance = context;
    window.setTimeout(() => { void instance.close().catch(() => {}); }, 550);
    return true;
  } catch {
    if (context) void context.close().catch(() => {});
    return false;
  }
}
