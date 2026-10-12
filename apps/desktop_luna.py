"""0.1.3 experimental Core-owned Luna delegation for Realtime Mini overlap.

The client can request *reasoning only*. Requests are rebound to the observed user
transcript (not model-supplied tool arguments). Late results never cross turns.
Computer actions, current-data tools, and memory retrieval are not enabled here.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from time import monotonic
from typing import Any

from core.intelligence import DelegationMode, DelegationOrchestrator, DelegationRequest, DelegationStatus


class DesktopLunaDelegator:
    """One current voice turn per desktop session, using the existing Core route."""

    def __init__(
        self,
        *,
        orchestrator: DelegationOrchestrator,
        conversation: Any,
        notify: Callable[[dict[str, Any]], Awaitable[None]],
        transcript_timeout: float = 6.0,
        result_hold_seconds: float = 0.0,
    ) -> None:
        self.orchestrator = orchestrator
        self.conversation = conversation
        self.notify = notify
        self.transcript_timeout = transcript_timeout
        if not 0 <= result_hold_seconds <= 20:
            raise ValueError("result_hold_seconds must be in [0, 20]")
        self.result_hold_seconds = result_hold_seconds
        self.current_turn = 0
        self._texts: dict[int, str] = {}
        self._events: dict[int, asyncio.Event] = {}
        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._selected_turns: set[int] = set()
        self._provider_lock = asyncio.Lock()
        self._executing_turn = 0
        self._closed = False

    def new_turn(self, turn: int) -> None:
        if self._closed or turn <= self.current_turn or turn <= 0:
            return
        self.current_turn = turn
        self._texts = {turn: self._texts[turn]} if turn in self._texts else {}
        self._events = {turn: self._events[turn]} if turn in self._events else {}
        self._selected_turns.intersection_update({turn})
        if self._executing_turn and self._executing_turn != turn:
            asyncio.create_task(self._cancel_core(self._executing_turn), name="luna-superseded-cancel")

    def transcript(self, turn: int, text: str) -> None:
        clean = " ".join(str(text).split())
        if self._closed or turn <= 0 or not clean or len(clean) > 4000:
            return
        self.new_turn(turn)
        if turn != self.current_turn:
            return
        self._texts[turn] = clean
        self._events.setdefault(turn, asyncio.Event()).set()

    def selected(self, turn: int) -> bool:
        """Selection only: no model-controlled arguments, no action capabilities."""
        if self._closed or turn <= 0 or turn != self.current_turn or turn in self._selected_turns:
            return False
        self._selected_turns.add(turn)
        self._tasks[turn] = asyncio.create_task(self._execute(turn), name=f"jarvis-luna-turn-{turn}")
        return True

    async def _cancel_core(self, expected_turn: int) -> None:
        if expected_turn <= 0 or self._executing_turn != expected_turn:
            return  # Never cancel a newer Core request through a stale signal.
        try:
            await self.conversation.cancel_active_turn("superseded Jarvis voice turn")
        except Exception:
            pass

    async def cancel(self) -> None:
        self.current_turn += 1
        self._texts.clear()
        for event in self._events.values():
            event.set()
        self._events.clear()
        if self._executing_turn:
            asyncio.create_task(self._cancel_core(self._executing_turn), name="luna-interrupt-cancel")

    async def close(self) -> None:
        self._closed = True
        await self.cancel()
        # Do not forcibly cancel the task while Core is in its turn-finally
        # logic: cooperative provider cancellation must return Core to LISTENING.
        if self._tasks:
            done, pending = await asyncio.wait(tuple(self._tasks.values()), timeout=2)
            for task in done:
                try: task.result()
                except Exception: pass
            # Remaining tasks are stale and cannot notify any future session.

    async def _execute(self, turn: int) -> None:
        started = monotonic()
        try:
            event = self._events.setdefault(turn, asyncio.Event())
            if turn not in self._texts:
                await asyncio.wait_for(event.wait(), timeout=self.transcript_timeout)
            if self._closed or turn != self.current_turn:
                return
            goal = self._texts.get(turn, "")
            if not goal:
                await self._result(turn, "unavailable", "I couldn't confirm what you asked. Could you repeat that?", started)
                return
            async with self._provider_lock:
                if self._closed or turn != self.current_turn:
                    return
                # Core's terminal ERROR or DEGRADED state survives the failed
                # turn by design. Recover only for a fresh authorized request
                # after its previous active trace has finished.
                recover = getattr(self.conversation, "recover_idle_after_terminal_failure", None)
                if callable(recover) and recover():
                    print(f"[Jarvis Luna] turn={turn} | phase=core_recovered | "
                          "reason=previous_terminal_failure", flush=True)
                self._executing_turn = turn
                print(f"[Jarvis Luna] turn={turn} | phase=core_started | authority=core", flush=True)
                try:
                    result = await self.orchestrator.execute(
                        DelegationRequest(goal=goal, mode=DelegationMode.REASONING),
                        conversation=self.conversation,
                    )
                finally:
                    self._executing_turn = 0
            if self._closed or turn != self.current_turn:
                return
            # Live-only, opt-in cancellation validation. Core has already
            # completed; hold the verified result privately so user speech
            # or sleep can supersede it before ANY audio is authorized.
            # Never enable in the ordinary Luna launch mode.
            if self.result_hold_seconds:
                print(f"[Jarvis Luna Cancel Test] turn={turn} | phase=holding_result "
                      f"| seconds={self.result_hold_seconds:g} | authority=none", flush=True)
                await asyncio.sleep(self.result_hold_seconds)
                if self._closed or turn != self.current_turn:
                    print(f"[Jarvis Luna Cancel Test] turn={turn} | phase=stale_result_discarded "
                          "| voice_delivered=false", flush=True)
                    return
                print(f"[Jarvis Luna Cancel Test] turn={turn} | phase=releasing_current_result", flush=True)
            if result.status is DelegationStatus.COMPLETED and result.text.strip():
                await self._result(turn, "completed", result.text.strip(), started,
                                   route=result.decision.route_name or "unknown")
            else:
                await self._result(turn, str(result.status.value),
                                   "I couldn't complete that request with Luna. Please try again.", started)
        except asyncio.TimeoutError:
            if not self._closed and turn == self.current_turn:
                await self._result(turn, "unavailable", "I couldn't confirm what you asked. Could you repeat that?", started)
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                message = str(exc).lower()
                category = "core_busy" if "foreground turn is already active" in message else (
                    "core_not_ready" if "core state=" in message else "runtime_error")
            else:
                category = "provider_or_runtime_failure"
            print(f"[Jarvis Luna] turn={turn} | phase=error | error={type(exc).__name__} "
                  f"| category={category}", flush=True)
            if not self._closed and turn == self.current_turn:
                await self._result(turn, "failed",
                                   "I couldn't complete that request through Core. Please try again.", started)
        finally:
            self._tasks.pop(turn, None)

    async def _result(self, turn: int, status: str, answer: str, started: float, *, route: str = "n/a") -> None:
        if self._closed or turn != self.current_turn:
            return
        # Cap single spoken reply; no file operations, tool execution, or state
        # changing results cross this boundary. The provider remains Core-owned.
        safe_text = answer[:3000]
        elapsed = round((monotonic() - started) * 1000)
        print(f"[Jarvis Luna] turn={turn} | phase=result | status={status} | route={route} "
              f"| elapsed_ms={elapsed} | text_chars={len(safe_text)} | authority=core", flush=True)
        await self.notify({"kind": "core_luna_result", "turn": turn, "status": status, "text": safe_text})
