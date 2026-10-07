'use strict';

const { app, BrowserWindow, dialog, session } = require('electron');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const http = require('node:http');
const net = require('node:net');
const path = require('node:path');

const CORE_HOST = '127.0.0.1';
const CORE_PORT = 8765;
const CORE_URL = `http://${CORE_HOST}:${CORE_PORT}`;
const HEALTH_URL = `${CORE_URL}/api/desktop/health`;
const START_TIMEOUT_MS = 45000;
const HEALTH_POLL_MS = 250;

let mainWindow = null;
let coreProcess = null;
let coreOwned = false;
let quitting = false;
let gracefulQuitStarted = false;

app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');

function projectRoot() {
  return path.resolve(__dirname, '..', '..', '..');
}

function pythonExecutable() {
  const root = projectRoot();
  const candidates = [];
  if (process.env.VIRTUAL_ENV) {
    candidates.push(path.join(process.env.VIRTUAL_ENV, 'Scripts', 'python.exe'));
    candidates.push(path.join(process.env.VIRTUAL_ENV, 'bin', 'python'));
  }
  candidates.push(path.join(root, '.venv', 'Scripts', 'python.exe'));
  candidates.push(path.join(root, '.venv', 'bin', 'python'));
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  return process.platform === 'win32' ? 'python' : 'python3';
}

function healthCheck(timeoutMs = 1200) {
  return new Promise((resolve) => {
    const request = http.get(HEALTH_URL, { timeout: timeoutMs }, (response) => {
      let body = '';
      response.setEncoding('utf8');
      response.on('data', (chunk) => { body += chunk; });
      response.on('end', () => {
        if (response.statusCode !== 200) return resolve(false);
        try {
          const payload = JSON.parse(body);
          resolve(payload.status === 'ok');
        } catch (_) {
          resolve(false);
        }
      });
    });
    request.on('timeout', () => { request.destroy(); resolve(false); });
    request.on('error', () => resolve(false));
  });
}

function portInUse() {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: CORE_HOST, port: CORE_PORT });
    socket.setTimeout(600);
    socket.on('connect', () => { socket.destroy(); resolve(true); });
    socket.on('timeout', () => { socket.destroy(); resolve(false); });
    socket.on('error', () => resolve(false));
  });
}

async function waitForCore() {
  const deadline = Date.now() + START_TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (await healthCheck()) return true;
    if (coreProcess && coreProcess.exitCode !== null) return false;
    await new Promise((resolve) => setTimeout(resolve, HEALTH_POLL_MS));
  }
  return false;
}

async function startCore() {
  if (await healthCheck()) {
    coreOwned = false;
    return;
  }
  if (await portInUse()) {
    throw new Error(`Port ${CORE_PORT} is already in use by something that is not the Jarvis Desktop Alpha host.`);
  }

  const python = pythonExecutable();
  coreProcess = spawn(python, ['-m', 'apps.desktop_alpha', '--port', String(CORE_PORT)], {
    cwd: projectRoot(),
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  coreOwned = true;
  coreProcess.stdout.on('data', (data) => process.stdout.write(`[Jarvis Core] ${data}`));
  coreProcess.stderr.on('data', (data) => process.stderr.write(`[Jarvis Core] ${data}`));
  coreProcess.on('exit', (code, signal) => {
    const expected = quitting;
    coreProcess = null;
    if (!expected && mainWindow && !mainWindow.isDestroyed()) {
      dialog.showErrorBox('Jarvis Core stopped', `The local Jarvis Core process exited unexpectedly (${signal || code || 'unknown'}).`);
      app.quit();
    }
  });

  if (!(await waitForCore())) {
    throw new Error('Jarvis Core did not become ready before the desktop startup timeout.');
  }
}

function configureMediaPermissions() {
  const allowed = (url) => String(url || '').startsWith(CORE_URL);
  session.defaultSession.setPermissionCheckHandler((_webContents, permission, requestingOrigin) => {
    return permission === 'media' && allowed(requestingOrigin);
  });
  session.defaultSession.setPermissionRequestHandler((_webContents, permission, callback, details) => {
    callback(permission === 'media' && allowed(details.requestingUrl));
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 900,
    height: 760,
    minWidth: 680,
    minHeight: 620,
    backgroundColor: '#070a10',
    autoHideMenuBar: true,
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      // Local wake capture must continue when the Jarvis window is minimized.
      // The renderer pauses no Core authority; this only keeps client media timers alive.
      backgroundThrottling: false,
    },
  });

  mainWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  mainWindow.webContents.on('will-navigate', (event, targetUrl) => {
    if (!String(targetUrl).startsWith(CORE_URL)) event.preventDefault();
  });
  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.on('closed', () => { mainWindow = null; });
  mainWindow.loadURL(CORE_URL);
}

function postEndSession() {
  return new Promise((resolve) => {
    const request = http.request(`${CORE_URL}/api/realtime/end`, {
      method: 'POST',
      timeout: 1500,
      headers: { 'Content-Length': '0' },
    }, (response) => {
      response.resume();
      response.on('end', resolve);
    });
    request.on('timeout', () => { request.destroy(); resolve(); });
    request.on('error', resolve);
    request.end();
  });
}

async function stopOwnedCore() {
  if (!coreOwned || !coreProcess) return;
  await postEndSession();
  await new Promise((resolve) => setTimeout(resolve, 120));
  if (coreProcess && coreProcess.exitCode === null) coreProcess.kill('SIGTERM');
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (!mainWindow) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  });

  app.whenReady().then(async () => {
    try {
      configureMediaPermissions();
      await startCore();
      createWindow();
    } catch (error) {
      dialog.showErrorBox('Jarvis Desktop Alpha could not start', String(error && error.message ? error.message : error));
      app.quit();
    }
  });

  app.on('window-all-closed', () => app.quit());

  app.on('before-quit', (event) => {
    quitting = true;
    if (!coreOwned || gracefulQuitStarted) return;
    event.preventDefault();
    gracefulQuitStarted = true;
    stopOwnedCore().finally(() => {
      coreOwned = false;
      app.quit();
    });
  });
}
