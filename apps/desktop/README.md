# Jarvis Desktop Alpha (0.1.0)

The desktop app is intentionally a **thin client**. Electron owns native window/process lifecycle, React owns presentation and client WebRTC, and the loopback Python host owns the authoritative `JarvisRuntime`, Realtime session brokering, and Core delegation.

The first UI is intentionally minimal:

- a centered code-native Jarvis avatar,
- live Jarvis transcript beneath the avatar while he speaks,
- one small typed-input field beneath the transcript,
- visual states for connecting, ready, listening, thinking, speaking, working, and error.

No memory, permission, tool, task, or model authority is implemented in the renderer.

## First-time setup

From the project root with the Python `.venv` already configured:

```powershell
npm install
```

## Run the desktop alpha

```powershell
npm run desktop
```

`npm run desktop` builds the React renderer and starts Electron. Electron supervises exactly one loopback Python desktop host at `127.0.0.1:8765`; do **not** manually start a second Core on that port.

The OpenAI API key remains in the local `.env` read by Python and is never shipped into the renderer.
