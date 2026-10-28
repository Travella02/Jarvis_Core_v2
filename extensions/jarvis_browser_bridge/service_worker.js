"use strict";

const CORE_WS = "ws://127.0.0.1:8765/api/browser/ws?client=jarvis-browser-bridge-v1";
const RECONNECT_MIN_MS = 500;
const RECONNECT_MAX_MS = 5000;
const KEEPALIVE_MS = 20000;
const RECONNECT_ALARM = "jarvis-browser-bridge-reconnect";
const BRIDGE_CAPABILITIES = Object.freeze([
  "tabs_list", "snapshot", "navigate", "navigate_target_guarded", "search", "tab_new", "tab_switch", "tab_close", "back", "forward", "refresh", "wait",
  "click", "type", "select", "scroll",
  "media_control", "media_volume", "media_mute", "media_seek", "media_rate", "media_fullscreen",
  "media_fullscreen_prepare_native", "media_fullscreen_state_native"
]);
let socket = null;
let reconnectTimer = null;
let reconnectDelay = RECONNECT_MIN_MS;
let keepaliveTimer = null;
let connecting = false;
const fullscreenWindowStates = new Map();

function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

function browserIdentity() {
  const ua = navigator.userAgent || "";
  const edge = ua.match(/Edg\/([\d.]+)/i);
  if (edge) return {browser_name: "Microsoft Edge", browser_version: edge[1] || ""};
  const chrome = ua.match(/Chrome\/([\d.]+)/i);
  if (chrome) return {browser_name: "Google Chrome", browser_version: chrome[1] || ""};
  return {browser_name: "Chromium", browser_version: ""};
}

async function instanceId() {
  const existing = await chrome.storage.local.get(["jarvisBridgeInstanceId"]);
  if (existing.jarvisBridgeInstanceId) return String(existing.jarvisBridgeInstanceId);
  const id = crypto.randomUUID();
  await chrome.storage.local.set({jarvisBridgeInstanceId: id});
  return id;
}

function urlSupported(url) {
  return /^https?:\/\//i.test(String(url || ""));
}

async function activeTab() {
  const [tab] = await chrome.tabs.query({active: true, lastFocusedWindow: true});
  if (!tab) return {};
  return {
    id: Number(tab.id || 0),
    title: String(tab.title || ""),
    url: String(tab.url || ""),
    window_id: Number(tab.windowId || 0)
  };
}

async function listTabs() {
  const tabs = await chrome.tabs.query({});
  return tabs.map((tab) => ({
    id: Number(tab.id || 0),
    title: String(tab.title || ""),
    url: String(tab.url || ""),
    active: Boolean(tab.active),
    window_id: Number(tab.windowId || 0)
  })).filter((tab) => tab.id > 0);
}

async function sendContent(tabId, operation, args = {}) {
  try {
    return await chrome.tabs.sendMessage(tabId, {__jarvis_browser_bridge: true, operation, arguments: args});
  } catch (firstError) {
    const tab = await chrome.tabs.get(tabId);
    if (!urlSupported(tab?.url)) throw new Error("unsupported_page_scheme");
    try {
      await chrome.scripting.executeScript({target: {tabId}, files: ["content.js"]});
      await sleep(60);
      return await chrome.tabs.sendMessage(tabId, {__jarvis_browser_bridge: true, operation, arguments: args});
    } catch (secondError) {
      throw new Error(String(secondError?.message || firstError?.message || "content_script_unavailable"));
    }
  }
}

async function snapshotCommand() {
  const tab = await activeTab();
  const tabs = await listTabs();
  if (!tab.id) return {ok: true, active_tab: {}, tabs, page: {supported: false, reason: "no_active_tab", elements: [], text: ""}};
  if (!urlSupported(tab.url)) {
    return {
      ok: true,
      active_tab: tab,
      tabs,
      page: {supported: false, reason: "browser_internal_or_unsupported_page", url: tab.url, title: tab.title, elements: [], text: ""}
    };
  }
  const response = await sendContent(tab.id, "snapshot", {});
  if (!response?.ok) throw new Error(response?.error || "snapshot_failed");
  return {ok: true, active_tab: tab, tabs, page: response.page || {supported: false, reason: "empty_snapshot", elements: [], text: ""}};
}

async function waitForTabSettled(tabId, timeoutMs = 5000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const tab = await chrome.tabs.get(tabId);
      if (!tab || tab.status === "complete") return;
    } catch (_) { return; }
    await sleep(120);
  }
}

async function executeYouTubePlayerMainWorld(tabId, operation, args = {}) {
  try {
    const results = await chrome.scripting.executeScript({
      target: {tabId},
      world: "MAIN",
      func: async (op, input) => {
        const player = document.getElementById("movie_player");
        const video = document.querySelector("video.html5-main-video, #movie_player video");
        if (!player || !(video instanceof HTMLMediaElement)) return {handled: false};
        const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
        const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
        // Treat the actual HTMLMediaElement as the physical playback authority.
        // YouTube's player getters can lag behind an action even after the user can
        // already see/hear the result, which caused truthful actions to be reported
        // as verification failures. Player APIs remain useful for issuing commands
        // and for UI-owned state such as volume, but playback/time verification
        // polls the media element that is actually rendering the video.
        const currentTime = () => number(video.currentTime, typeof player.getCurrentTime === "function" ? number(player.getCurrentTime(), 0) : 0);
        const duration = () => number(video.duration, typeof player.getDuration === "function" ? number(player.getDuration(), 0) : 0);
        const isPlaying = () => !video.paused && !video.ended;
        const waitFor = async (predicate, timeoutMs = 1400, intervalMs = 90) => {
          const deadline = Date.now() + timeoutMs;
          while (Date.now() < deadline) {
            try { if (predicate()) return true; } catch (_) {}
            await delay(intervalMs);
          }
          try { return Boolean(predicate()); } catch (_) { return false; }
        };

        if (op === "media_control") {
          const action = String(input.action || "pause").toLowerCase();
          if (action === "pause") {
            if (typeof player.pauseVideo === "function") player.pauseVideo(); else video.pause();
            const verified = await waitFor(() => video.paused || video.ended);
            return {
              handled: true, ok: true, verified,
              media_state: (video.paused || video.ended) ? "paused" : "playing",
              player_state: typeof player.getPlayerState === "function" ? Number(player.getPlayerState()) : null,
              summary: verified ? "Paused the video." : "The video did not pause."
            };
          }
          if (typeof player.playVideo === "function") player.playVideo(); else { try { await video.play(); } catch (_) {} }
          const verified = await waitFor(() => !video.paused && !video.ended);
          return {
            handled: true, ok: true, verified,
            media_state: (!video.paused && !video.ended) ? "playing" : "paused",
            player_state: typeof player.getPlayerState === "function" ? Number(player.getPlayerState()) : null,
            summary: verified ? "Resumed the video." : "The video did not resume."
          };
        }

        if (op === "media_volume") {
          const percent = Math.max(0, Math.min(100, number(input.percent, 0)));
          if (typeof player.setVolume !== "function" || typeof player.getVolume !== "function") return {handled: false};
          player.setVolume(percent);
          if (percent > 0 && typeof player.unMute === "function") player.unMute();
          await delay(180);
          // Re-apply once after YouTube's player state settles so the native slider,
          // saved player preference and actual audio all agree.
          player.setVolume(percent);
          if (percent > 0 && typeof player.unMute === "function") player.unMute();
          await delay(220);
          const actual = Math.max(0, Math.min(100, Math.round(number(player.getVolume(), video.volume * 100))));
          const muted = typeof player.isMuted === "function" ? Boolean(player.isMuted()) : Boolean(video.muted);
          const verified = Math.abs(actual - Math.round(percent)) <= 1 && (percent === 0 || !muted);
          return {handled: true, ok: true, verified, media_volume: actual, media_muted: muted, summary: verified ? `Set the video volume to ${Math.round(percent)}%.` : `The video volume stayed at ${actual}%.`};
        }

        if (op === "media_mute") {
          const wanted = Boolean(input.muted);
          if (wanted && typeof player.mute === "function") player.mute();
          else if (!wanted && typeof player.unMute === "function") player.unMute();
          else video.muted = wanted;
          await delay(140);
          const actual = typeof player.isMuted === "function" ? Boolean(player.isMuted()) : Boolean(video.muted);
          const verified = actual === wanted;
          return {handled: true, ok: true, verified, media_muted: actual, summary: verified ? (wanted ? "Muted the video." : "Unmuted the video.") : "The video's mute state did not change."};
        }

        if (op === "media_seek") {
          const total = duration();
          let target = currentTime();
          if (Number.isFinite(Number(input.position_seconds))) target = Number(input.position_seconds);
          else target += number(input.delta_seconds, 0);
          target = Math.max(0, total > 0 ? Math.min(total, target) : target);
          if (typeof player.seekTo === "function") player.seekTo(target, true); else video.currentTime = target;
          if (Boolean(input.resume)) {
            if (typeof player.playVideo === "function") player.playVideo(); else { try { await video.play(); } catch (_) {} }
          }
          const tolerance = Math.max(2.0, Math.min(5.0, Math.abs(number(input.delta_seconds, 0)) * 0.12));
          const positionVerified = await waitFor(() => {
            const observed = currentTime();
            return Math.abs(observed - target) <= tolerance || (target === 0 && observed <= 3.0);
          }, 1600, 90);
          const playbackVerified = !Boolean(input.resume) || await waitFor(() => isPlaying(), 1200, 90);
          const actual = currentTime();
          const verified = positionVerified && playbackVerified;
          return {
            handled: true, ok: true, verified, media_time_seconds: actual, media_duration_seconds: total || null,
            media_state: isPlaying() ? "playing" : "paused",
            player_time_seconds: typeof player.getCurrentTime === "function" ? number(player.getCurrentTime(), actual) : null,
            summary: verified ? `Moved the video to ${Math.max(0, Math.round(actual))} seconds.` : "The video did not move to the requested position."
          };
        }

        if (op === "media_rate") {
          const wanted = Math.max(0.25, Math.min(4, number(input.rate, 1)));
          if (typeof player.setPlaybackRate === "function") player.setPlaybackRate(wanted);
          video.defaultPlaybackRate = wanted;
          video.playbackRate = wanted;
          const verified = await waitFor(() => Math.abs(number(video.playbackRate, 1) - wanted) <= 0.01, 900, 80);
          const actual = number(video.playbackRate, 1);
          return {handled: true, ok: true, verified, media_rate: actual, player_rate: typeof player.getPlaybackRate === "function" ? number(player.getPlaybackRate(), actual) : null, summary: verified ? `Set playback speed to ${wanted}x.` : `Playback speed stayed at ${actual}x.`};
        }
        return {handled: false};
      },
      args: [operation, args],
    });
    const value = results?.[0]?.result;
    return value && typeof value === "object" ? value : null;
  } catch (_) {
    return null;
  }
}

function mediaTabScore(tab, activeId, preferYouTube, preferredTabId = 0) {
  const url = String(tab?.url || "").toLowerCase();
  const isYouTube = /https?:\/\/(?:www\.)?youtube\.com\//.test(url);
  const isWatch = isYouTube && /\/watch(?:\?|$)/.test(url);
  let score = 0;
  if (Number(tab?.id || 0) === Number(preferredTabId || 0)) score += 2400;
  if (Number(tab?.id || 0) === Number(activeId || 0)) score += 500;
  if (Boolean(tab?.audible)) score += 800;
  if (isWatch) score += preferYouTube ? 1100 : 450;
  else if (isYouTube) score += preferYouTube ? 700 : 180;
  if (Boolean(tab?.active)) score += 80;
  return score;
}

async function executeMediaOnBestTab(operation, args = {}) {
  const tabs = (await chrome.tabs.query({})).filter((tab) => Number(tab?.id || 0) > 0 && urlSupported(tab?.url));
  const active = await activeTab();
  const preferYouTube = Boolean(args.prefer_youtube);
  const preferredTabId = Number(args.preferred_tab_id || 0);
  tabs.sort((left, right) => mediaTabScore(right, active.id, preferYouTube, preferredTabId) - mediaTabScore(left, active.id, preferYouTube, preferredTabId));
  // Once Jarvis has grounded a media tab, never spill the same media command into
  // a different user tab. If that tab is still open but no longer has usable
  // media, fail truthfully instead of restarting/altering media elsewhere.
  const preferredTab = preferredTabId > 0 ? tabs.find((tab) => Number(tab?.id || 0) === preferredTabId) : null;
  const candidateTabs = preferredTab ? [preferredTab] : tabs;
  let lastError = null;
  for (const tab of candidateTabs) {
    // A freshly navigated SPA can expose its video a moment after the tab itself is
    // usable. Retry the structural content operation briefly before moving on.
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        const isYouTubeWatch = /https?:\/\/(?:www\.)?youtube\.com\/watch(?:\?|$)/i.test(String(tab?.url || ""));
        let response = null;
        if (isYouTubeWatch && ["media_control", "media_volume", "media_mute", "media_seek", "media_rate"].includes(operation)) {
          const pageOwned = await executeYouTubePlayerMainWorld(Number(tab.id), operation, args);
          if (pageOwned?.handled) response = pageOwned;
        }
        if (!response) response = await sendContent(Number(tab.id), operation, args);
        if (response?.ok) {
          const windowId = Number(tab.windowId || 0);
          let windowStateVerified = true;
          if (operation === "media_fullscreen" && String(args.action || "enter") === "enter" && response.request_window_fullscreen && windowId > 0) {
            let priorState = "normal";
            try {
              const windowInfo = await chrome.windows.get(windowId);
              priorState = String(windowInfo?.state || "normal");
              if (!fullscreenWindowStates.has(windowId)) fullscreenWindowStates.set(windowId, priorState);
              await chrome.windows.update(windowId, {focused: true, state: "fullscreen"});
              await sleep(180);
              const updated = await chrome.windows.get(windowId);
              windowStateVerified = String(updated?.state || "") === "fullscreen";
              if (windowStateVerified) {
                let pageState = await sendContent(Number(tab.id), "media_fullscreen_verify", {});
                if (!pageState?.verified) {
                  await sendContent(Number(tab.id), "media_fullscreen_reconcile", {});
                  await sleep(140);
                  pageState = await sendContent(Number(tab.id), "media_fullscreen_verify", {});
                }
                windowStateVerified = Boolean(pageState?.verified);
              }
            } catch (_) { windowStateVerified = false; }
            if (!windowStateVerified) {
              try { await sendContent(Number(tab.id), "media_fullscreen", {action: "exit"}); } catch (_) {}
              const restoreState = String(fullscreenWindowStates.get(windowId) || priorState || "normal");
              fullscreenWindowStates.delete(windowId);
              try { await chrome.windows.update(windowId, {focused: true, state: restoreState}); } catch (_) {}
              response = {...response, summary: "I couldn't make the video fullscreen.", media_fullscreen: false, verified: false, request_window_fullscreen: false};
            }
          }
          if (operation === "media_fullscreen" && String(args.action || "") === "exit" && windowId > 0 && fullscreenWindowStates.has(windowId)) {
            const priorState = String(fullscreenWindowStates.get(windowId) || "normal");
            fullscreenWindowStates.delete(windowId);
            try {
              await chrome.windows.update(windowId, {focused: true, state: priorState});
              const updated = await chrome.windows.get(windowId);
              windowStateVerified = String(updated?.state || "") === priorState;
            } catch (_) { windowStateVerified = false; }
          }
          const {ok: _ok, ...details} = response;
          if (operation === "media_fullscreen" && details.verified === true) details.verified = windowStateVerified;
          return {
            ok: true,
            ...details,
            summary: response.summary || `${operation} completed.`,
            risk: response.risk || "normal",
            media_tab: {id: Number(tab.id), title: String(tab.title || ""), url: String(tab.url || "")},
            active_tab: await activeTab(),
          };
        }
        lastError = new Error(response?.error || `${operation}_failed`);
      } catch (error) {
        lastError = error;
      }
      if (attempt < 2) await sleep(attempt === 0 ? 120 : 260);
    }
  }
  throw new Error(String(lastError?.message || `${operation}_failed`));
}

async function executeCommand(operation, args) {
  if (operation === "tabs_list") return {ok: true, active_tab: await activeTab(), tabs: await listTabs()};
  if (operation === "snapshot") return await snapshotCommand();
  if (operation === "navigate") {
    const url = String(args.url || "").trim();
    let parsed;
    try { parsed = new URL(url); } catch (_) { throw new Error("navigate_invalid_url"); }
    if (parsed.protocol !== "https:") throw new Error("navigate_requires_https_url");
    const tabId = Number(args.tab_id || 0);
    const expectedHost = String(args.expected_host || "").toLowerCase();
    // v2 Core may ONLY navigate a specific live tab whose current hostname
    // still matches the independently authorized site. A focus change cannot
    // silently redirect an unrelated tab between switch and navigate.
    if (!Number.isSafeInteger(tabId) || tabId < 1 || !expectedHost ||
        !/^[a-z0-9.-]+$/.test(expectedHost)) throw new Error("navigate_requires_verified_tab");
    const normalizedHost = (host) => String(host || "").toLowerCase().replace(/^www\./, "");
    const tab = await chrome.tabs.get(tabId);
    if (!tab || !urlSupported(tab.url) ||
        normalizedHost(new URL(tab.url).hostname) !== expectedHost ||
        normalizedHost(parsed.hostname) !== expectedHost) {
      throw new Error("navigate_target_changed");
    }
    await chrome.tabs.update(tabId, {url});
    try { await chrome.windows.update(tab.windowId, {focused: true}); } catch (_) {}
    await chrome.tabs.update(tabId, {active: true});
    if (args.wait_for_load !== false) await waitForTabSettled(tabId);
    const updated = await chrome.tabs.get(tabId);
    return {
      ok: true, summary: "Navigated the verified tab.",
      active_tab: {id: tabId, title: String(updated.title || ""),
        url: String(updated.url || ""), window_id: Number(updated.windowId || 0)}
    };
  }
  if (operation === "search") {
    const query = String(args.query || "").trim();
    if (!query) throw new Error("search_query_required");
    const tab = await activeTab();
    if (!tab.id) throw new Error("no_active_tab");
    const url = `https://www.google.com/search?q=${encodeURIComponent(query)}`;
    await chrome.tabs.update(tab.id, {url});
    if (args.wait_for_load !== false) await waitForTabSettled(tab.id);
    return {ok: true, summary: `Searched the web for ${query}.`, active_tab: await activeTab()};
  }
  if (operation === "tab_new") {
    const raw = String(args.url || "").trim();
    if (raw && !/^https?:\/\//i.test(raw)) throw new Error("new_tab_url_requires_http_url");
    const tab = await chrome.tabs.create(raw ? {url: raw, active: true} : {active: true});
    if (tab.id && args.wait_for_load !== false) await waitForTabSettled(tab.id, 3500);
    return {ok: true, summary: "Opened a new tab.", active_tab: await activeTab()};
  }
  if (operation === "tab_switch") {
    const tabId = Number(args.tab_id || 0);
    if (!tabId) throw new Error("tab_id_required");
    const tab = await chrome.tabs.get(tabId);
    await chrome.windows.update(tab.windowId, {focused: true});
    await chrome.tabs.update(tabId, {active: true});
    return {ok: true, summary: `Switched to ${tab.title || "the tab"}.`, active_tab: await activeTab()};
  }
  if (operation === "tab_close") {
    const tabId = Number(args.tab_id || 0);
    if (!tabId) throw new Error("tab_id_required");
    const tab = await chrome.tabs.get(tabId);
    await chrome.tabs.remove(tabId);
    return {ok: true, summary: `Closed ${tab.title || "the tab"}.`, active_tab: await activeTab()};
  }
  if (["back", "forward", "refresh"].includes(operation)) {
    const tab = await activeTab();
    if (!tab.id) throw new Error("no_active_tab");
    if (operation === "back") await chrome.tabs.goBack(tab.id);
    else if (operation === "forward") await chrome.tabs.goForward(tab.id);
    else await chrome.tabs.reload(tab.id);
    if (args.wait_for_load !== false) await waitForTabSettled(tab.id, 4000);
    return {ok: true, summary: operation === "back" ? "Went back." : operation === "forward" ? "Went forward." : "Refreshed the page.", active_tab: await activeTab()};
  }
  if (operation === "wait") {
    await sleep(Math.max(100, Math.min(5000, Number(args.wait_ms || 600))));
    return {ok: true, summary: "Waited for the page.", active_tab: await activeTab()};
  }
  if (["media_control", "media_volume", "media_mute", "media_seek", "media_rate", "media_fullscreen", "media_fullscreen_prepare_native", "media_fullscreen_state_native"].includes(operation)) {
    return await executeMediaOnBestTab(operation, args);
  }
  if (["click", "type", "select", "scroll"].includes(operation)) {
    const tab = await activeTab();
    if (!tab.id) throw new Error("no_active_tab");
    if (!urlSupported(tab.url)) throw new Error("unsupported_page_scheme");
    const response = await sendContent(tab.id, operation, args);
    if (!response?.ok) throw new Error(response?.error || `${operation}_failed`);
    if (operation === "click") {
      // Return promptly; the core owns any read-after-write settling needed by an agentic task.
      await sleep(80);
    }
    return {ok: true, summary: response.summary || `${operation} completed.`, risk: response.risk || "normal", active_tab: await activeTab()};
  }
  throw new Error(`unsupported_browser_operation:${operation}`);
}

async function sendHello() {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    void connectBridge();
    return;
  }
  const identity = browserIdentity();
  socket.send(JSON.stringify({
    type: "hello",
    instance_id: await instanceId(),
    extension_version: chrome.runtime.getManifest().version,
    capabilities: BRIDGE_CAPABILITIES,
    ...identity,
    active_tab: await activeTab()
  }));
}

function clearTimers() {
  clearTimeout(reconnectTimer);
  reconnectTimer = null;
  clearInterval(keepaliveTimer);
  keepaliveTimer = null;
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    void connectBridge();
  }, reconnectDelay);
  reconnectDelay = Math.min(RECONNECT_MAX_MS, Math.round(reconnectDelay * 1.6));
}

async function connectBridge() {
  if (connecting || (socket && [WebSocket.OPEN, WebSocket.CONNECTING].includes(socket.readyState))) return;
  connecting = true;
  clearTimers();
  try {
    socket = new WebSocket(CORE_WS);
    socket.onopen = () => {
      reconnectDelay = RECONNECT_MIN_MS;
      void sendHello();
      keepaliveTimer = setInterval(() => {
        if (!socket || socket.readyState !== WebSocket.OPEN) return;
        void activeTab().then((tab) => socket?.send(JSON.stringify({type: "heartbeat", active_tab: tab}))).catch(() => {});
      }, KEEPALIVE_MS);
    };
    socket.onmessage = (event) => {
      void (async () => {
        let message;
        try { message = JSON.parse(String(event.data || "{}")); } catch (_) { return; }
        if (message?.type !== "command" || !message.id) return;
        try {
          const result = await executeCommand(String(message.operation || ""), message.arguments || {});
          if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({type: "result", id: message.id, ok: true, result}));
        } catch (error) {
          if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({type: "result", id: message.id, ok: false, error: String(error?.message || error || "browser_command_failed")}));
        }
      })();
    };
    socket.onclose = () => { clearTimers(); socket = null; scheduleReconnect(); };
    socket.onerror = () => { try { socket?.close(); } catch (_) {} };
  } catch (_) {
    socket = null;
    scheduleReconnect();
  } finally {
    connecting = false;
  }
}

async function ensureReconnectAlarm() {
  try {
    const existing = await chrome.alarms.get(RECONNECT_ALARM);
    if (!existing) chrome.alarms.create(RECONNECT_ALARM, {periodInMinutes: 0.5});
  } catch (_) {}
}

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm?.name === RECONNECT_ALARM) void connectBridge();
});
chrome.runtime.onInstalled.addListener(() => { void ensureReconnectAlarm(); void connectBridge(); });
chrome.runtime.onStartup.addListener(() => { void ensureReconnectAlarm(); void connectBridge(); });
chrome.tabs.onActivated.addListener(() => void sendHello());
chrome.tabs.onUpdated.addListener((_tabId, changeInfo) => { if (changeInfo.status === "complete" || changeInfo.url) void sendHello(); });
void ensureReconnectAlarm();
void connectBridge();
