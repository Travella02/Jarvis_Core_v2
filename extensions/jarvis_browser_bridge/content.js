"use strict";

(() => {
  if (globalThis.__jarvisBrowserBridgeContentInstalled) return;
  globalThis.__jarvisBrowserBridgeContentInstalled = true;

  const elementMap = new Map();
  let snapshotSerial = 0;
  const MAX_ELEMENTS = 220;
  const MAX_TEXT = 24000;
  const COMMIT_RE = /\b(?:submit|send|publish|post|buy|purchase|checkout|pay|transfer|delete|remove|unsubscribe|place\s+(?:my|the|an?)\s+order|confirm\s+(?:order|purchase|payment|booking)|book\s+(?:now|it)|reserve\s+(?:now|it)|sign\s+(?:it|this)|apply\s+(?:now|for))\b/i;

  function normalize(value) {
    return String(value ?? "").replace(/\s+/g, " ").trim();
  }

  function rendered(element) {
    if (!(element instanceof Element)) return false;
    const style = getComputedStyle(element);
    if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity || 1) === 0) return false;
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function inViewport(element) {
    const rect = element.getBoundingClientRect();
    return rect.bottom >= -2 && rect.right >= -2 && rect.top <= innerHeight + 2 && rect.left <= innerWidth + 2;
  }

  function labelText(element) {
    const aria = normalize(element.getAttribute("aria-label"));
    if (aria) return aria;
    const labelledBy = normalize(element.getAttribute("aria-labelledby"));
    if (labelledBy) {
      const joined = labelledBy.split(/\s+/).map((id) => normalize(document.getElementById(id)?.innerText || document.getElementById(id)?.textContent || "")).filter(Boolean).join(" ");
      if (joined) return joined;
    }
    if (element.id) {
      const label = document.querySelector(`label[for="${CSS.escape(element.id)}"]`);
      const text = normalize(label?.innerText || label?.textContent || "");
      if (text) return text;
    }
    const wrappingLabel = element.closest("label");
    const wrappingText = normalize(wrappingLabel?.innerText || wrappingLabel?.textContent || "");
    if (wrappingText) return wrappingText;
    const placeholder = normalize(element.getAttribute("placeholder"));
    if (placeholder) return placeholder;
    const title = normalize(element.getAttribute("title"));
    if (title) return title;
    if (element instanceof HTMLInputElement) {
      if ((element.type || "").toLowerCase() === "password") return "Password field";
      if (["button", "submit", "reset"].includes((element.type || "").toLowerCase())) return normalize(element.value);
    }
    return normalize(element.innerText || element.textContent || "");
  }

  function elementRisk(element, label) {
    const type = normalize(element.getAttribute("type")).toLowerCase();
    if (type === "password" || sensitiveField(element)) return "sensitive";
    const combined = `${label} ${normalize(element.getAttribute("name"))} ${normalize(element.getAttribute("value"))}`;
    if (COMMIT_RE.test(combined)) return "external_commit";
    return "normal";
  }

  function sensitiveField(element) {
    if (!(element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement)) return false;
    const type = normalize(element.getAttribute("type")).toLowerCase();
    const autocomplete = normalize(element.getAttribute("autocomplete")).toLowerCase();
    const identity = `${normalize(element.getAttribute("name"))} ${normalize(element.id)} ${normalize(element.getAttribute("aria-label"))} ${normalize(element.getAttribute("placeholder"))}`;
    if (type === "password") return true;
    if (/^(?:cc-|one-time-code|current-password|new-password)/i.test(autocomplete)) return true;
    return /\b(?:ssn|social\s*security|card\s*(?:number|no)|credit\s*card|debit\s*card|cvv|cvc|security\s*code|api\s*key|access\s*token|secret\s*key|private\s*key|seed\s*phrase|recovery\s*phrase)\b/i.test(identity);
  }

  function exposedValue(element) {
    if (sensitiveField(element)) return "";
    if (element instanceof HTMLInputElement) {
      const type = (element.type || "text").toLowerCase();
      if (type === "password") return "";
      if (["checkbox", "radio"].includes(type)) return element.checked ? "checked" : "unchecked";
      if (["button", "submit", "reset", "file"].includes(type)) return "";
      return normalize(element.value).slice(0, 800);
    }
    if (element instanceof HTMLTextAreaElement || element instanceof HTMLSelectElement) return normalize(element.value).slice(0, 800);
    if (element.isContentEditable) return normalize(element.innerText).slice(0, 800);
    return "";
  }

  function interactiveElements() {
    const selector = [
      "a[href]", "button", "input:not([type='hidden'])", "textarea", "select",
      "[role='button']", "[role='link']", "[role='tab']", "[role='menuitem']",
      "[contenteditable='true']", "[onclick]"
    ].join(",");
    const seen = new Set();
    const viewportNodes = [];
    const offscreenLinks = [];
    for (const element of document.querySelectorAll(selector)) {
      if (seen.has(element) || !rendered(element)) continue;
      seen.add(element);
      if (inViewport(element)) {
        viewportNodes.push(element);
      } else if (element instanceof HTMLAnchorElement && /^https?:\/\//i.test(String(element.href || "")) && normalize(element.innerText || element.textContent || "")) {
        offscreenLinks.push(element);
      }
    }
    return [...viewportNodes, ...offscreenLinks].slice(0, MAX_ELEMENTS);
  }

  function snapshot() {
    snapshotSerial += 1;
    elementMap.clear();
    const elements = [];
    let index = 0;
    for (const element of interactiveElements()) {
      index += 1;
      const id = `e${snapshotSerial}_${index}`;
      elementMap.set(id, element);
      const label = labelText(element).slice(0, 360);
      const href = element instanceof HTMLAnchorElement ? String(element.href || "").slice(0, 1200) : "";
      elements.push({
        id,
        tag: element.tagName.toLowerCase(),
        role: normalize(element.getAttribute("role")),
        label,
        href,
        input_type: normalize(element.getAttribute("type")).toLowerCase(),
        value: exposedValue(element),
        risk: elementRisk(element, label),
        disabled: Boolean(element.disabled || element.getAttribute("aria-disabled") === "true")
      });
    }
    const text = normalize(document.body?.innerText || "").slice(0, MAX_TEXT);
    const mediaElement = preferredMediaElement();
    const media = mediaElement instanceof HTMLMediaElement ? {
      present: true,
      kind: mediaElement.tagName.toLowerCase(),
      state: (mediaElement.paused || mediaElement.ended) ? "paused" : "playing",
      current_time_seconds: Number.isFinite(Number(mediaElement.currentTime)) ? Number(mediaElement.currentTime) : 0,
      duration_seconds: Number.isFinite(Number(mediaElement.duration)) ? Number(mediaElement.duration) : 0,
      volume_percent: Math.round(Math.max(0, Math.min(1, Number(mediaElement.volume || 0))) * 100),
      muted: Boolean(mediaElement.muted),
      rate: Number.isFinite(Number(mediaElement.playbackRate)) ? Number(mediaElement.playbackRate) : 1,
      fullscreen: Boolean(document.fullscreenElement || jarvisImmersiveState)
    } : {present: false};
    return {
      supported: true,
      url: location.href,
      title: document.title || "",
      text,
      elements,
      media,
      scroll_y: Math.round(scrollY || 0),
      scroll_height: Math.round(document.documentElement?.scrollHeight || document.body?.scrollHeight || 0),
      viewport_height: Math.round(innerHeight || 0)
    };
  }

  function resolveElement(id) {
    const element = elementMap.get(String(id || ""));
    if (!element || !element.isConnected) throw new Error("stale_element_reference");
    return element;
  }

  function clickElement(id, allowConsequential) {
    const element = resolveElement(id);
    const label = labelText(element);
    const risk = elementRisk(element, label);
    if (risk === "sensitive") throw new Error("sensitive_element_blocked");
    if (risk === "external_commit" && !allowConsequential) throw new Error("consequential_action_requires_confirmation");
    if (element.disabled || element.getAttribute("aria-disabled") === "true") throw new Error("element_disabled");
    element.scrollIntoView({block: "center", inline: "nearest", behavior: "auto"});
    element.click();
    return {summary: `Clicked ${label || element.tagName.toLowerCase()}.`, risk};
  }

  function setNativeValue(element, value) {
    if (element instanceof HTMLInputElement) {
      const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
      descriptor?.set?.call(element, value);
    } else if (element instanceof HTMLTextAreaElement) {
      const descriptor = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value");
      descriptor?.set?.call(element, value);
    } else if (element.isContentEditable) {
      element.textContent = value;
    } else {
      throw new Error("element_not_editable");
    }
  }

  function typeInto(id, text) {
    const element = resolveElement(id);
    if (sensitiveField(element)) throw new Error("sensitive_fields_are_blocked");
    if (element instanceof HTMLInputElement && (element.type || "").toLowerCase() === "password") throw new Error("password_fields_are_blocked");
    if (!(element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement || element.isContentEditable)) throw new Error("element_not_editable");
    if (element.disabled || element.getAttribute("aria-disabled") === "true") throw new Error("element_disabled");
    element.focus();
    setNativeValue(element, String(text ?? ""));
    element.dispatchEvent(new InputEvent("input", {bubbles: true, inputType: "insertText", data: null}));
    element.dispatchEvent(new Event("change", {bubbles: true}));
    return {summary: `Updated ${labelText(element) || "the field"}.`};
  }

  function selectOption(id, option) {
    const element = resolveElement(id);
    if (!(element instanceof HTMLSelectElement)) throw new Error("element_not_select");
    const wanted = normalize(option).toLowerCase();
    const match = [...element.options].find((item) => normalize(item.textContent).toLowerCase() === wanted || normalize(item.value).toLowerCase() === wanted)
      || [...element.options].find((item) => normalize(item.textContent).toLowerCase().includes(wanted));
    if (!match) throw new Error("select_option_not_found");
    element.value = match.value;
    element.dispatchEvent(new Event("input", {bubbles: true}));
    element.dispatchEvent(new Event("change", {bubbles: true}));
    return {summary: `Selected ${normalize(match.textContent) || match.value}.`};
  }

  function scrollPage(direction) {
    const amount = Math.max(320, Math.round(innerHeight * 0.72));
    if (direction === "top") scrollTo({top: 0, behavior: "auto"});
    else if (direction === "bottom") scrollTo({top: document.documentElement.scrollHeight, behavior: "auto"});
    else if (direction === "up") scrollBy({top: -amount, behavior: "auto"});
    else scrollBy({top: amount, behavior: "auto"});
    return {summary: `Scrolled ${direction || "down"}.`};
  }

  const MEDIA_VERIFY_DELAY_MS = 140;
  let jarvisImmersiveState = null;

  function delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function preferredMediaElement() {
    // YouTube can expose preview/ad/media elements alongside the actual player.
    // Prefer the structural main player before falling back to generic playing media.
    const youtubeMain = document.querySelector("video.html5-main-video, #movie_player video");
    if (youtubeMain instanceof HTMLMediaElement && youtubeMain.readyState >= 1) return youtubeMain;
    const media = [...document.querySelectorAll("video, audio")].filter((item) => item instanceof HTMLMediaElement);
    return media.find((item) => !item.paused && !item.ended && item.readyState >= 1 && rendered(item))
      || media.find((item) => !item.paused && !item.ended && item.readyState >= 1)
      || media.find((item) => item.readyState >= 1 && rendered(item))
      || media.find((item) => item.readyState >= 1)
      || media[0]
      || null;
  }

  function youtubePlayButton() {
    return document.querySelector("button.ytp-play-button, .ytp-play-button");
  }

  async function mediaControl(action) {
    const media = preferredMediaElement();
    if (!(media instanceof HTMLMediaElement)) throw new Error("media_element_not_found");
    const requested = normalize(action).toLowerCase();
    if (requested === "pause") {
      if (!media.paused) media.pause();
      await delay(MEDIA_VERIFY_DELAY_MS);
      if (!media.paused && /(?:^|\.)youtube\.com$/i.test(location.hostname)) {
        const button = youtubePlayButton();
        const label = normalize(button?.getAttribute?.("aria-label") || "").toLowerCase();
        if (button instanceof HTMLElement && label.includes("pause")) button.click();
        await delay(MEDIA_VERIFY_DELAY_MS);
      }
      const verified = Boolean(media.paused);
      return {summary: verified ? "Paused the video." : "The video did not pause.", media_state: media.paused ? "paused" : "playing", verified};
    }
    if (requested === "play") {
      if (media.paused) {
        try { await media.play(); } catch (_) {}
      }
      await delay(MEDIA_VERIFY_DELAY_MS);
      if (media.paused && /(?:^|\.)youtube\.com$/i.test(location.hostname)) {
        const button = youtubePlayButton();
        const label = normalize(button?.getAttribute?.("aria-label") || "").toLowerCase();
        if (button instanceof HTMLElement && label.includes("play")) button.click();
        await delay(MEDIA_VERIFY_DELAY_MS);
      }
      const verified = !media.paused && !media.ended;
      return {summary: verified ? "Resumed the video." : "The video did not resume.", media_state: verified ? "playing" : "paused", verified};
    }
    throw new Error("unsupported_media_action");
  }

  async function mediaVolume(percent) {
    const media = preferredMediaElement();
    if (!(media instanceof HTMLMediaElement)) throw new Error("media_element_not_found");
    const clamped = Math.max(0, Math.min(100, Number(percent || 0)));
    const wanted = clamped / 100;
    try {
      media.volume = wanted;
      if (clamped > 0) media.muted = false;
      media.dispatchEvent(new Event("volumechange", {bubbles: true}));
    } catch (_) {}
    await delay(MEDIA_VERIFY_DELAY_MS);
    // YouTube can replace its main video during SPA transitions. Re-resolve once
    // and apply the requested state to the actual main player if that happened.
    const resolved = preferredMediaElement();
    if (resolved instanceof HTMLMediaElement && resolved !== media) {
      try {
        resolved.volume = wanted;
        if (clamped > 0) resolved.muted = false;
        resolved.dispatchEvent(new Event("volumechange", {bubbles: true}));
      } catch (_) {}
      await delay(MEDIA_VERIFY_DELAY_MS);
    }
    const target = preferredMediaElement();
    if (!(target instanceof HTMLMediaElement)) throw new Error("media_element_not_found");
    const actual = Math.max(0, Math.min(100, Math.round(Number(target.volume || 0) * 100)));
    const verified = Math.abs(actual - Math.round(clamped)) <= 1 && (clamped === 0 || !target.muted);
    return {summary: verified ? `Set the video volume to ${Math.round(clamped)}%.` : `The video volume stayed at ${actual}%.`, media_volume: actual, media_muted: Boolean(target.muted), verified};
  }

  async function mediaMute(muted) {
    const media = preferredMediaElement();
    if (!(media instanceof HTMLMediaElement)) throw new Error("media_element_not_found");
    media.muted = Boolean(muted);
    media.dispatchEvent(new Event("volumechange", {bubbles: true}));
    await delay(MEDIA_VERIFY_DELAY_MS);
    const verified = Boolean(media.muted) === Boolean(muted);
    return {summary: verified ? (media.muted ? "Muted the video." : "Unmuted the video.") : "The video's mute state did not change.", media_muted: Boolean(media.muted), verified};
  }

  async function mediaSeek(args = {}) {
    const media = preferredMediaElement();
    if (!(media instanceof HTMLMediaElement)) throw new Error("media_element_not_found");
    const duration = Number.isFinite(media.duration) && media.duration > 0 ? media.duration : null;
    let target = Number(media.currentTime || 0);
    if (Number.isFinite(Number(args.position_seconds))) target = Number(args.position_seconds);
    else target += Number(args.delta_seconds || 0);
    target = Math.max(0, duration ? Math.min(duration, target) : target);
    try { media.currentTime = target; } catch (_) {}
    if (Boolean(args.resume)) {
      try { await media.play(); } catch (_) {}
    }
    await delay(MEDIA_VERIFY_DELAY_MS);
    const actual = Number(media.currentTime || 0);
    const tolerance = Math.max(1.5, Math.min(4, Math.abs(Number(args.delta_seconds || 0)) * 0.08));
    const positionVerified = Math.abs(actual - target) <= tolerance || (target === 0 && actual <= 2.0);
    const playbackVerified = !Boolean(args.resume) || (!media.paused && !media.ended);
    const verified = positionVerified && playbackVerified;
    const rounded = Math.max(0, Math.round(actual));
    return {summary: verified ? `Moved the video to ${rounded} seconds.` : "The video did not move to the requested position.", media_time_seconds: actual, media_duration_seconds: duration, media_state: media.paused ? "paused" : "playing", verified};
  }

  async function mediaRate(rate) {
    const media = preferredMediaElement();
    if (!(media instanceof HTMLMediaElement)) throw new Error("media_element_not_found");
    const clamped = Math.max(0.25, Math.min(4, Number(rate || 1)));
    media.defaultPlaybackRate = clamped;
    media.playbackRate = clamped;
    await delay(MEDIA_VERIFY_DELAY_MS);
    const actual = Number(media.playbackRate || 1);
    const verified = Math.abs(actual - clamped) <= 0.01;
    return {summary: verified ? `Set playback speed to ${clamped}x.` : `Playback speed stayed at ${actual}x.`, media_rate: actual, verified};
  }

  function fullscreenPlayerTarget(media) {
    const youtubePlayer = document.querySelector("#movie_player, .html5-video-player");
    if (youtubePlayer instanceof HTMLElement && youtubePlayer.contains(media)) return youtubePlayer;
    return media instanceof HTMLElement ? media : null;
  }

  function immersiveGeometryVerified(state) {
    if (!state?.host?.isConnected || !(state.target instanceof HTMLElement)) return false;
    if (state.target.parentElement !== state.host) return false;
    const hostRect = state.host.getBoundingClientRect();
    const targetRect = state.target.getBoundingClientRect();
    const viewportWidth = Math.max(1, Number(innerWidth || document.documentElement?.clientWidth || 0));
    const viewportHeight = Math.max(1, Number(innerHeight || document.documentElement?.clientHeight || 0));
    const hostCoversViewport = hostRect.left <= 1 && hostRect.top <= 1 && hostRect.right >= viewportWidth - 1 && hostRect.bottom >= viewportHeight - 1;
    const targetCoversViewport = targetRect.width >= viewportWidth * 0.9 && targetRect.height >= viewportHeight * 0.9;
    let hostOwnsViewport = true;
    if (typeof document.elementFromPoint === "function") {
      const points = [[0.05, 0.05], [0.5, 0.5], [0.95, 0.05], [0.05, 0.95], [0.95, 0.95]];
      hostOwnsViewport = points.every(([x, y]) => {
        const top = document.elementFromPoint(Math.max(1, viewportWidth * x), Math.max(1, viewportHeight * y));
        return !top || state.host === top || state.host.contains(top);
      });
    }
    let pageIsolationVerified = true;
    const root = state.root instanceof HTMLElement ? state.root : null;
    if (root && typeof getComputedStyle === "function") {
      pageIsolationVerified = [...root.children].every((child) => {
        if (!(child instanceof HTMLElement) || child === state.host) return true;
        return getComputedStyle(child).display === "none";
      });
    }
    return hostCoversViewport && targetCoversViewport && hostOwnsViewport && pageIsolationVerified;
  }

  function suppressImmersiveSibling(state, element) {
    if (!(element instanceof HTMLElement) || element === state.host) return;
    if (!state.suppressedSiblings.has(element)) {
      state.suppressedSiblings.set(element, {
        display: element.style.getPropertyValue("display"),
        priority: element.style.getPropertyPriority("display"),
      });
    }
    if (element.style.getPropertyValue("display") !== "none" || element.style.getPropertyPriority("display") !== "important") {
      element.style.setProperty("display", "none", "important");
    }
  }

  function installImmersiveIsolation(state) {
    const root = state.root;
    if (!(root instanceof HTMLElement)) return;
    for (const child of [...root.children]) suppressImmersiveSibling(state, child);
    if (typeof MutationObserver === "function") {
      state.isolationObserver = new MutationObserver((records) => {
        for (const record of records) {
          if (record.type === "childList") {
            for (const node of record.addedNodes || []) suppressImmersiveSibling(state, node);
          } else if (record.type === "attributes") {
            suppressImmersiveSibling(state, record.target);
          }
        }
      });
      state.isolationObserver.observe(root, {childList: true, attributes: true, subtree: false, attributeFilter: ["style"]});
    }
  }

  function restoreImmersiveIsolation(state) {
    try { state.isolationObserver?.disconnect?.(); } catch (_) {}
    for (const [element, previous] of state.suppressedSiblings || []) {
      if (!(element instanceof HTMLElement)) continue;
      if (previous.display) element.style.setProperty("display", previous.display, previous.priority || "");
      else element.style.removeProperty("display");
    }
    state.suppressedSiblings?.clear?.();
  }

  function enterJarvisImmersive(media) {
    if (jarvisImmersiveState && immersiveGeometryVerified(jarvisImmersiveState)) return true;
    if (jarvisImmersiveState) exitJarvisImmersive();
    const target = fullscreenPlayerTarget(media);
    if (!(target instanceof HTMLElement)) return false;
    const parent = target.parentNode;
    if (!(parent instanceof Node)) return false;

    // A fixed YouTube player can still be constrained by transformed/contained page
    // ancestors. Put the live player in a top-level Jarvis portal instead. This keeps
    // the real video/control DOM and event listeners intact while preventing page,
    // description, recommendation, and third-party overlay layers from bleeding
    // through the immersive fallback.
    const host = document.createElement("div");
    host.setAttribute("data-jarvis-immersive-host", "true");
    Object.assign(host.style, {
      position: "fixed",
      inset: "0",
      width: "100vw",
      height: "100vh",
      margin: "0",
      padding: "0",
      overflow: "hidden",
      zIndex: "2147483647",
      background: "#000",
      isolation: "isolate",
    });

    const root = document.body || document.documentElement;
    jarvisImmersiveState = {
      host,
      root,
      target,
      targetParent: parent,
      targetNextSibling: target.nextSibling,
      targetStyle: target.getAttribute("style"),
      media,
      mediaStyle: media.getAttribute("style"),
      bodyOverflow: document.body?.style?.overflow ?? "",
      htmlOverflow: document.documentElement?.style?.overflow ?? "",
      suppressedSiblings: new Map(),
      isolationObserver: null,
    };

    root.appendChild(host);
    installImmersiveIsolation(jarvisImmersiveState);
    host.appendChild(target);
    Object.assign(target.style, {
      position: "relative",
      inset: "auto",
      width: "100%",
      height: "100%",
      maxWidth: "none",
      maxHeight: "none",
      margin: "0",
      zIndex: "1",
      background: "#000",
    });
    if (media !== target) {
      Object.assign(media.style, {width: "100%", height: "100%", maxWidth: "none", maxHeight: "none", objectFit: "contain"});
    }
    if (document.body) document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    return immersiveGeometryVerified(jarvisImmersiveState);
  }

  function exitJarvisImmersive() {
    const state = jarvisImmersiveState;
    if (!state) return false;
    const target = state.target;
    if (target instanceof HTMLElement) {
      const parent = state.targetParent;
      if (parent instanceof Node && parent.isConnected) {
        const next = state.targetNextSibling;
        if (next instanceof Node && next.parentNode === parent) parent.insertBefore(target, next);
        else parent.appendChild(target);
      }
      if (state.targetStyle === null) target.removeAttribute("style");
      else target.setAttribute("style", state.targetStyle);
    }
    const media = state.media;
    if (media instanceof HTMLElement && state.mediaStyle !== undefined) {
      if (state.mediaStyle === null) media.removeAttribute("style");
      else media.setAttribute("style", state.mediaStyle);
    }
    restoreImmersiveIsolation(state);
    if (state.host instanceof HTMLElement) state.host.remove();
    if (document.body) document.body.style.overflow = state.bodyOverflow;
    document.documentElement.style.overflow = state.htmlOverflow;
    jarvisImmersiveState = null;
    return true;
  }

  async function mediaFullscreen(action) {
    const requested = normalize(action).toLowerCase() === "exit" ? "exit" : "enter";
    const media = preferredMediaElement();
    if (!(media instanceof HTMLMediaElement)) throw new Error("media_element_not_found");
    if (requested === "exit") {
      const hadJarvisImmersive = Boolean(jarvisImmersiveState);
      if (document.fullscreenElement && typeof document.exitFullscreen === "function") {
        try { await document.exitFullscreen(); } catch (_) {}
        await delay(MEDIA_VERIFY_DELAY_MS);
      }
      if (jarvisImmersiveState) exitJarvisImmersive();
      await delay(40);
      const verified = !document.fullscreenElement && !jarvisImmersiveState;
      return {summary: verified ? "Exited fullscreen." : "I couldn't exit fullscreen.", media_fullscreen: !verified, verified, fullscreen_mode: hadJarvisImmersive ? "jarvis_immersive" : "native", request_window_restore: hadJarvisImmersive};
    }

    if (document.fullscreenElement) return {summary: "The video is already fullscreen.", media_fullscreen: true, verified: true, fullscreen_mode: "native"};
    if (jarvisImmersiveState && immersiveGeometryVerified(jarvisImmersiveState)) {
      return {summary: "The video is already fullscreen.", media_fullscreen: true, verified: true, fullscreen_mode: "jarvis_immersive", request_window_fullscreen: true};
    }

    // Do not synthesize a click on YouTube's fullscreen button. Chromium can reject
    // the underlying Fullscreen API call because a voice/runtime message is not a
    // trusted user gesture while YouTube still mutates its own fullscreen CSS. That
    // half-entered state is what caused page descriptions/recommendations/extension
    // overlays to remain visible over the video during live acceptance.
    const target = fullscreenPlayerTarget(media);
    const userActivation = Boolean(navigator.userActivation?.isActive);
    if (userActivation && target && typeof target.requestFullscreen === "function") {
      try { await target.requestFullscreen(); } catch (_) {}
      await delay(MEDIA_VERIFY_DELAY_MS);
      if (document.fullscreenElement) return {summary: "Made the video fullscreen.", media_fullscreen: true, verified: true, fullscreen_mode: "native"};
    }

    const immersive = enterJarvisImmersive(media);
    await delay(60);
    const verified = immersive && Boolean(jarvisImmersiveState) && immersiveGeometryVerified(jarvisImmersiveState);
    if (!verified && jarvisImmersiveState) exitJarvisImmersive();
    return {summary: verified ? "Made the video fullscreen." : "I couldn't make the video fullscreen.", media_fullscreen: verified, verified, fullscreen_mode: verified ? "jarvis_immersive" : "none", request_window_fullscreen: verified};
  }

  function nativeFullscreenState() {
    const media = preferredMediaElement();
    if (!(media instanceof HTMLMediaElement)) return {verified: false, media_fullscreen: false, fullscreen_mode: "none", ready: false};
    const player = fullscreenPlayerTarget(media);
    const fullscreenElement = document.fullscreenElement;
    const nativeFullscreen = Boolean(
      fullscreenElement && player instanceof HTMLElement && (
        fullscreenElement === player || fullscreenElement.contains(media) || player.contains(fullscreenElement)
      )
    );
    const youtubeFullscreen = Boolean(player instanceof HTMLElement && player.classList.contains("ytp-fullscreen"));
    const viewportWidth = Math.max(1, Number(innerWidth || document.documentElement?.clientWidth || 0));
    const viewportHeight = Math.max(1, Number(innerHeight || document.documentElement?.clientHeight || 0));
    const rect = player instanceof HTMLElement ? player.getBoundingClientRect() : media.getBoundingClientRect();
    const coversViewport = rect.left <= 2 && rect.top <= 2 && rect.right >= viewportWidth - 2 && rect.bottom >= viewportHeight - 2;
    const active = Boolean((nativeFullscreen || youtubeFullscreen) && coversViewport);
    return {
      verified: true,
      ready: true,
      media_fullscreen: active,
      fullscreen_mode: active ? "youtube_native" : "none",
      native_fullscreen_element: nativeFullscreen,
      youtube_fullscreen_class: youtubeFullscreen,
      viewport_covered: coversViewport,
    };
  }

  function prepareNativeFullscreenShortcut() {
    const media = preferredMediaElement();
    if (!(media instanceof HTMLMediaElement)) throw new Error("media_element_not_found");
    const player = fullscreenPlayerTarget(media);
    const active = document.activeElement;
    if (active instanceof HTMLElement && (
      active.matches("input, textarea, select, [contenteditable='true'], [contenteditable='']") || active.isContentEditable
    )) {
      try { active.blur(); } catch (_) {}
    }
    const focusTarget = player instanceof HTMLElement ? player : media;
    if (!focusTarget.hasAttribute("tabindex")) focusTarget.setAttribute("tabindex", "-1");
    try { focusTarget.focus({preventScroll: true}); } catch (_) { try { focusTarget.focus(); } catch (_) {} }
    return {prepared: true, ...nativeFullscreenState()};
  }

  async function verifyOrReconcileJarvisImmersive(reconcile = false) {
    if (!jarvisImmersiveState) return {verified: false, fullscreen_mode: "none"};
    if (immersiveGeometryVerified(jarvisImmersiveState)) return {verified: true, fullscreen_mode: "jarvis_immersive"};
    if (!reconcile) return {verified: false, fullscreen_mode: "jarvis_immersive"};
    const media = preferredMediaElement() || jarvisImmersiveState.media;
    exitJarvisImmersive();
    await delay(40);
    if (!(media instanceof HTMLMediaElement) || !media.isConnected) return {verified: false, fullscreen_mode: "none"};
    const entered = enterJarvisImmersive(media);
    await delay(100);
    return {verified: Boolean(entered && jarvisImmersiveState && immersiveGeometryVerified(jarvisImmersiveState)), fullscreen_mode: jarvisImmersiveState ? "jarvis_immersive" : "none"};
  }

  async function executeContentOperation(operation, args) {
    if (operation === "ping") return {ok: true};
    if (operation === "snapshot") return {ok: true, page: snapshot()};
    if (operation === "click") return {ok: true, ...clickElement(args.element_id, Boolean(args.allow_consequential))};
    if (operation === "type") return {ok: true, ...typeInto(args.element_id, args.text)};
    if (operation === "select") return {ok: true, ...selectOption(args.element_id, args.option)};
    if (operation === "scroll") return {ok: true, ...scrollPage(String(args.direction || "down"))};
    if (operation === "media_control") return {ok: true, ...await mediaControl(String(args.action || "pause"))};
    if (operation === "media_volume") return {ok: true, ...await mediaVolume(Number(args.percent || 0))};
    if (operation === "media_mute") return {ok: true, ...await mediaMute(Boolean(args.muted))};
    if (operation === "media_seek") return {ok: true, ...await mediaSeek(args)};
    if (operation === "media_rate") return {ok: true, ...await mediaRate(Number(args.rate || 1))};
    if (operation === "media_fullscreen") return {ok: true, ...await mediaFullscreen(String(args.action || "enter"))};
    if (operation === "media_fullscreen_prepare_native") return {ok: true, ...prepareNativeFullscreenShortcut()};
    if (operation === "media_fullscreen_state_native") return {ok: true, ...nativeFullscreenState()};
    if (operation === "media_fullscreen_verify") return {ok: true, ...await verifyOrReconcileJarvisImmersive(false)};
    if (operation === "media_fullscreen_reconcile") return {ok: true, ...await verifyOrReconcileJarvisImmersive(true)};
    throw new Error(`unsupported_content_operation:${operation}`);
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!message || message.__jarvis_browser_bridge !== true) return undefined;
    Promise.resolve(executeContentOperation(String(message.operation || ""), message.arguments || {}))
      .then((result) => sendResponse(result))
      .catch((error) => sendResponse({ok: false, error: String(error?.message || error || "content_command_failed")}));
    return true;
  });
})();
