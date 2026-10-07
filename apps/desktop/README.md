# Jarvis Desktop Alpha (0.1.1)

The desktop app is a **thin client** over authoritative Jarvis Core. Electron owns native process/window lifecycle, React owns presentation and client WebRTC media, and the loopback Python host owns `JarvisRuntime`, local wake policy, Realtime session brokering, and Core delegation.

## Presence lifecycle

- The app starts **SLEEPING**.
- Sleeping microphone PCM stays local: renderer -> loopback `/ws/wake` -> Silero + whisper.cpp.
- `Jarvis, <request>` wakes and preserves `<request>` into the new Realtime session.
- While awake, Realtime 2.1 Mini + Cedar + WebRTC handles continuous conversation.
- Explicit sleep intent or 60 seconds of inactivity closes Realtime and re-arms the local wake lane.
- Typing while asleep wakes Jarvis into the same Realtime conversation.

Presence (`sleeping/awake`) is separate from activity (`listening/thinking/speaking/working/error`). The OpenAI API key remains in Python/Core and is never shipped into React.

The current local wake implementation uses whisper.cpp because the alpha already ships that provider boundary. This is **not** a claim that full Whisper transcription is the final production wake-word engine; a lighter dedicated keyword spotter should be evaluated for low-end/mobile hardware later.

## First-time setup

```powershell
npm install
powershell -ExecutionPolicy Bypass -File .\scripts\setup_whisper_cpp.ps1 -Backend cuda
powershell -ExecutionPolicy Bypass -File .\scripts\setup_whisper_vad.ps1
```

## Run

```powershell
npm run desktop
```

Electron supervises exactly one loopback Python desktop host at `127.0.0.1:8765`; do not manually start another Core on that port.
