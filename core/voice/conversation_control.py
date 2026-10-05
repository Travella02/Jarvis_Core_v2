"""0.0.5 wake/sleep and continuous-conversation control.

Lifecycle (sleeping/awake) is deliberately separate from Conversation Core's
foreground activity state. Future modes such as working, researching, thinking,
or error can therefore coexist with an awake Jarvis without rewriting wake/sleep.
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from time import monotonic
from typing import Callable, Mapping

from core.intelligence import ReasoningPolicy
from core.voice.engine import VoiceLabEngine, VoiceTurnResult


_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def _normalized_words(text: str) -> tuple[str, ...]:
    return tuple(match.group(0).lower() for match in _WORD_RE.finditer(text))


def _parse_env_file(path: str | Path | None) -> dict[str, str]:
    if path is None:
        return {}
    target = Path(path)
    if not target.is_file():
        return {}
    result: dict[str, str] = {}
    for raw in target.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _environment(
    env: Mapping[str, str] | None = None,
    env_file: str | Path | None = None,
) -> dict[str, str]:
    merged = dict(os.environ)
    merged.update(_parse_env_file(env_file))
    if env is not None:
        merged.update(env)
    return merged


def _split_phrases(value: str | None, fallback: tuple[str, ...]) -> tuple[str, ...]:
    if value is None or not value.strip():
        return fallback
    parts = tuple(part.strip() for part in value.split("|") if part.strip())
    return parts or fallback


class VoicePresenceState(str, Enum):
    SLEEPING = "sleeping"
    AWAKE = "awake"


@dataclass(frozen=True, slots=True)
class WakeMatch:
    phrase: str
    command_text: str


@dataclass(frozen=True, slots=True)
class WakeSleepConfig:
    wake_phrases: tuple[str, ...] = ("hey jarvis", "jarvis")
    sleep_phrases: tuple[str, ...] = (
        "that's all",
        "that's all jarvis",
        "that is all",
        "that is all jarvis",
        "go to sleep",
        "go to sleep jarvis",
        "sleep jarvis",
        "goodnight jarvis",
        "good night jarvis",
    )
    idle_timeout_seconds: float = 60.0
    start_awake: bool = False

    def __post_init__(self) -> None:
        if self.idle_timeout_seconds <= 0:
            raise ValueError("idle_timeout_seconds must be positive")
        if not self.wake_phrases:
            raise ValueError("at least one wake phrase is required")
        wake = tuple(dict.fromkeys(item.strip() for item in self.wake_phrases if item.strip()))
        sleep = tuple(dict.fromkeys(item.strip() for item in self.sleep_phrases if item.strip()))
        if not wake:
            raise ValueError("at least one non-empty wake phrase is required")
        object.__setattr__(self, "wake_phrases", wake)
        object.__setattr__(self, "sleep_phrases", sleep)

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        env_file: str | Path | None = None,
    ) -> "WakeSleepConfig":
        source = _environment(env, env_file)
        defaults = cls()
        wake = _split_phrases(source.get("JARVIS_WAKE_PHRASES"), defaults.wake_phrases)
        sleep = _split_phrases(source.get("JARVIS_SLEEP_PHRASES"), defaults.sleep_phrases)
        timeout_raw = source.get("JARVIS_IDLE_SLEEP_SECONDS")
        timeout = float(timeout_raw) if timeout_raw else defaults.idle_timeout_seconds
        return cls(wake_phrases=wake, sleep_phrases=sleep, idle_timeout_seconds=timeout)


class WakePhraseDetector:
    """Match configurable wake phrases at the beginning of a full utterance.

    We intentionally wait for local STT to finish the complete utterance while
    sleeping, then strip only the wake phrase and immediately route the remainder
    as the user's command. No cloud request is made for speech that does not wake
    Jarvis.
    """

    def __init__(self, phrases: tuple[str, ...]) -> None:
        candidates: list[tuple[str, tuple[str, ...]]] = []
        for phrase in phrases:
            words = _normalized_words(phrase)
            if words:
                candidates.append((phrase, words))
        candidates.sort(key=lambda item: len(item[1]), reverse=True)
        self._phrases = tuple(candidates)

    def match(self, text: str) -> WakeMatch | None:
        matches = list(_WORD_RE.finditer(text))
        lowered = tuple(match.group(0).lower() for match in matches)
        for phrase, words in self._phrases:
            if len(lowered) < len(words) or lowered[: len(words)] != words:
                continue
            end = matches[len(words) - 1].end()
            remainder = text[end:].lstrip(" \t,;:.-!?—–")
            return WakeMatch(phrase=phrase, command_text=remainder.strip())
        return None


class SleepPhraseDetector:
    def __init__(self, phrases: tuple[str, ...]) -> None:
        self._phrases = frozenset(_normalized_words(item) for item in phrases if item.strip())

    def matches(self, text: str) -> bool:
        words = _normalized_words(text)
        return bool(words) and words in self._phrases


@dataclass(frozen=True, slots=True)
class VoiceSessionResult:
    completed_turns: int
    wake_count: int
    sleep_count: int
    interruption_count: int
    final_presence: VoicePresenceState


StatusCallback = Callable[[str], None]
TurnCallback = Callable[[VoiceTurnResult], None]
TranscriptCallback = Callable[[str, VoicePresenceState], None]


class ContinuousVoiceSession:
    """Always-listening 0.0.5 session controller.

    While awake, the next microphone capture begins as soon as the current user
    turn is submitted, so the user can preempt Jarvis during thinking, synthesis,
    or audible playback. Silero onset opens only a provisional candidate. Barge-in
    becomes authoritative only after the generic multi-signal confidence validator
    confirms speech; no words receive hard-coded interruption semantics.

    This remains a headset-first full-duplex path; production acoustic echo
    cancellation remains a later audio integration concern.
    """

    def __init__(
        self,
        *,
        engine: VoiceLabEngine,
        config: WakeSleepConfig | None = None,
        reasoning_policy: ReasoningPolicy | None = None,
    ) -> None:
        self.engine = engine
        self.config = config or WakeSleepConfig()
        self.reasoning_policy = reasoning_policy or ReasoningPolicy()
        self.presence = (
            VoicePresenceState.AWAKE
            if self.config.start_awake
            else VoicePresenceState.SLEEPING
        )
        self.wake_detector = WakePhraseDetector(self.config.wake_phrases)
        self.sleep_detector = SleepPhraseDetector(self.config.sleep_phrases)
        self._last_activity = monotonic()
        self._wake_count = 0
        self._sleep_count = 0
        self._interruption_count = 0

    def _emit_presence(self, state: VoicePresenceState, reason: str) -> None:
        previous = self.presence
        self.presence = state
        self.engine.conversation.event_bus.emit(
            "voice.presence.changed",
            origin="voice-session",
            conversation_id=self.engine.conversation.context.conversation_id,
            user_id=self.engine.conversation.context.user_id,
            device_id=self.engine.conversation.context.device_id,
            payload={"from": previous.value, "to": state.value, "reason": reason},
        )

    def wake(self, reason: str) -> None:
        if self.presence is VoicePresenceState.AWAKE:
            return
        self._wake_count += 1
        self._last_activity = monotonic()
        self._emit_presence(VoicePresenceState.AWAKE, reason)

    def sleep(self, reason: str) -> None:
        if self.presence is VoicePresenceState.SLEEPING:
            return
        self._sleep_count += 1
        self._emit_presence(VoicePresenceState.SLEEPING, reason)

    async def _cancel_listener(self, task: asyncio.Task) -> None:
        if task.done():
            await asyncio.gather(task, return_exceptions=True)
            return
        # Cooperative token cancellation first. Hard-cancelling the listener at
        # once can destroy nested audio/STT async generators while Windows queue
        # awaits are still live. Give the normal provider cleanup path time to
        # finish, then use Task.cancel only as a bounded fallback.
        await self.engine.cancel_capture("voice session listener cancelled")
        done, _ = await asyncio.wait({task}, timeout=1.5)
        if task not in done:
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def _listen_awake_with_idle(
        self,
        listen_task: asyncio.Task,
        speech_confirmed: asyncio.Event,
    ):
        """Wait for accepted speech or the true 60-second idle boundary.

        A provisional Silero candidate does not reset the inactivity timer. If the
        user begins speaking right on the boundary, however, give the candidate a
        short grace window to finish confidence validation instead of cancelling
        the microphone mid-utterance.
        """

        while True:
            if listen_task.done():
                return await listen_task
            if speech_confirmed.is_set():
                self._last_activity = monotonic()
                return await listen_task

            remaining = self.config.idle_timeout_seconds - (monotonic() - self._last_activity)
            if remaining <= 0:
                if getattr(self.engine, "capture_candidate_active", False):
                    await asyncio.sleep(0.10)
                    continue
                await self._cancel_listener(listen_task)
                return None

            event_task = asyncio.create_task(speech_confirmed.wait())
            done, _ = await asyncio.wait(
                {listen_task, event_task},
                timeout=remaining,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if listen_task in done:
                event_task.cancel()
                await asyncio.gather(event_task, return_exceptions=True)
                return await listen_task
            if event_task in done:
                self._last_activity = monotonic()
                return await listen_task
            event_task.cancel()
            await asyncio.gather(event_task, return_exceptions=True)

    async def run(
        self,
        *,
        max_completed_turns: int | None = None,
        on_status: StatusCallback | None = None,
        on_turn: TurnCallback | None = None,
        on_transcript: TranscriptCallback | None = None,
    ) -> VoiceSessionResult:
        if max_completed_turns is not None and max_completed_turns <= 0:
            raise ValueError("max_completed_turns must be positive when provided")

        completed = 0
        pending_capture = None

        while max_completed_turns is None or completed < max_completed_turns:
            if pending_capture is None:
                if on_status:
                    if self.presence is VoicePresenceState.SLEEPING:
                        on_status(
                            "Sleeping. Say a wake phrase and your request in one sentence, "
                            "for example: 'Hey Jarvis, what time is it?'"
                        )
                    else:
                        on_status("Awake and listening...")

                if self.presence is VoicePresenceState.AWAKE:
                    speech_confirmed = asyncio.Event()

                    def awake_confirmed(_event) -> None:
                        speech_confirmed.set()

                    unsubscribe = self.engine.conversation.event_bus.subscribe(
                        "voice.speech.confidence_confirmed", awake_confirmed
                    )
                    listen_task = asyncio.create_task(
                        self.engine.listen_once(), name="jarvis-awake-listener"
                    )
                    try:
                        pending_capture = await self._listen_awake_with_idle(
                            listen_task, speech_confirmed
                        )
                    finally:
                        unsubscribe()
                    if pending_capture is None:
                        self.sleep("60-second inactivity timeout")
                        continue
                else:
                    pending_capture = await self.engine.listen_once()

            transcript, latency, capture_trace = pending_capture
            pending_capture = None
            if on_transcript:
                on_transcript(transcript, self.presence)

            if self.presence is VoicePresenceState.SLEEPING:
                wake_match = self.wake_detector.match(transcript)
                if wake_match is None:
                    self.engine.conversation.event_bus.emit(
                        "voice.wake.ignored",
                        origin="voice-session",
                        trace=capture_trace,
                        conversation_id=self.engine.conversation.context.conversation_id,
                        payload={"transcript": transcript},
                    )
                    continue
                self.wake(f"wake phrase: {wake_match.phrase}")
                prompt = wake_match.command_text or transcript
                self.engine.conversation.event_bus.emit(
                    "voice.wake.detected",
                    origin="voice-session",
                    trace=capture_trace,
                    conversation_id=self.engine.conversation.context.conversation_id,
                    payload={
                        "wake_phrase": wake_match.phrase,
                        "command_text": wake_match.command_text,
                    },
                )
            else:
                prompt = transcript

            if self.sleep_detector.matches(prompt) or self.sleep_detector.matches(transcript):
                await self.engine.interrupt_response("explicit sleep command")
                self.sleep("explicit sleep command")
                self._last_activity = monotonic()
                continue

            self._last_activity = monotonic()
            response_task = asyncio.create_task(
                self.engine.respond_to_transcript(
                    prompt,
                    latency=latency,
                    capture_trace=capture_trace,
                    reasoning_policy=self.reasoning_policy,
                ),
                name="jarvis-response",
            )

            # Keep listening throughout the active turn. Silero onset is only a
            # provisional candidate; cancelling Jarvis waits for generic
            # multi-signal speech confidence. Accepted text still goes through
            # the normal Jarvis intelligence path with no keyword fast path.
            speech_confirmed = asyncio.Event()

            def active_speech_confirmed(_event) -> None:
                self._last_activity = monotonic()
                speech_confirmed.set()

            unsubscribe_confirmed = self.engine.conversation.event_bus.subscribe(
                "voice.speech.confidence_confirmed", active_speech_confirmed
            )
            listen_task = asyncio.create_task(
                self.engine.listen_once(lexical_interrupt_probe=True),
                name="jarvis-full-duplex-listener",
            )
            speech_waiter = asyncio.create_task(
                speech_confirmed.wait(), name="jarvis-interruption-confidence"
            )

            try:
                done, _ = await asyncio.wait(
                    {response_task, speech_waiter, listen_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                user_spoke = speech_waiter in done or (
                    listen_task in done and not listen_task.cancelled()
                )
                if user_spoke and not response_task.done():
                    self._interruption_count += 1
                    phase = getattr(self.engine, "_response_phase", None) or "active-turn"
                    self.engine.conversation.event_bus.emit(
                        "voice.barge_in.detected",
                        origin="voice-session",
                        conversation_id=self.engine.conversation.context.conversation_id,
                        payload={
                            "reason": "multi-signal speech confidence during active turn",
                            "phase": phase,
                            "authority": "multi-signal-confidence",
                        },
                    )
                    await self.engine.interrupt_response(
                        f"user interruption during {phase}"
                    )
                    result = await response_task
                    if on_turn:
                        on_turn(result)
                    if result.status not in {"completed", "interrupted", "cancelled"}:
                        return VoiceSessionResult(
                            completed, self._wake_count, self._sleep_count,
                            self._interruption_count, self.presence
                        )
                    completed += 1
                    # The same capture that triggered neural speech-start keeps
                    # recording until Whisper has the complete interruption text.
                    pending_capture = (
                        listen_task.result()
                        if listen_task.done()
                        else await listen_task
                    )
                else:
                    result = await response_task
                    self._last_activity = monotonic()
                    if on_turn:
                        on_turn(result)
                    if result.status not in {"completed", "interrupted", "cancelled"}:
                        await self._cancel_listener(listen_task)
                        return VoiceSessionResult(
                            completed, self._wake_count, self._sleep_count,
                            self._interruption_count, self.presence
                        )
                    completed += 1
                    if max_completed_turns is not None and completed >= max_completed_turns:
                        await self._cancel_listener(listen_task)
                        break
                    pending_capture = await self._listen_awake_with_idle(
                        listen_task, speech_confirmed
                    )
                    if pending_capture is None:
                        self.sleep("60-second inactivity timeout")
            finally:
                unsubscribe_confirmed()
                if not speech_waiter.done():
                    speech_waiter.cancel()
                await asyncio.gather(speech_waiter, return_exceptions=True)

        return VoiceSessionResult(
            completed_turns=completed,
            wake_count=self._wake_count,
            sleep_count=self._sleep_count,
            interruption_count=self._interruption_count,
            final_presence=self.presence,
        )
