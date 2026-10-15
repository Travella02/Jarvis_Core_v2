"""0.1.3 experimental Core-owned Luna delegation for Realtime Mini overlap.

The client can request *reasoning only*. Requests are rebound to the observed user
transcript (not model-supplied tool arguments). Late results never cross turns.
Computer actions, current-data tools, and memory retrieval are not enabled here.
"""
from __future__ import annotations

import asyncio
import re
import sys
import os
from collections.abc import Awaitable, Callable
from time import monotonic
from typing import Any

from core.intelligence import DelegationMode, DelegationOrchestrator, DelegationRequest, DelegationStatus
from apps.desktop_cancel_cue import play_native_hold_cue


def _safe_core_failure_fields(detail: str | None) -> dict[str, str]:
    """Recognize ONLY sanitized provider markers. Never print raw API error text.

    Provider messages, traceback text, user prompts and credentials are never
    included. Unknown details deliberately become ``unclassified``.
    """
    message = str(detail or "")
    http = re.search(r"\bHTTP ([1-5][0-9]{2})\b", message)
    error = re.search(r"\(([A-Za-z][A-Za-z0-9_]{0,79})(?:;|\))", message)
    code = re.search(r"(?:\bcode=)([A-Za-z0-9_.-]{1,64})(?:[;) ]|$)", message)
    param = re.search(r"(?:\bparam=)([A-Za-z0-9_.\[\]-]{1,80})(?:[;) ]|$)", message)
    fields = {
        "http_status": http.group(1) if http else "n/a",
        "error_type": error.group(1) if error else "n/a",
        "error_code": code.group(1) if code else "n/a",
        "error_param": param.group(1) if param else "n/a",
    }
    if not http and not error and not code and not param:
        fields["detail_class"] = (
            "incomplete_response" if message == "OpenAI response ended incomplete" else
            "provider_stream_ended" if message == "provider stream ended without a terminal event" else
            "unclassified"
        )
    else:
        fields["detail_class"] = "structured_provider_error"
    return fields


def _safe_core_budget_fields(orchestrator: Any, result: Any) -> dict[str, str]:
    """Server-side, response-ID matched, non-sensitive Core provider diagnostics.

    Never print arbitrary model names, response text, raw provider errors, IDs,
    context data, or account details. Unknown/mismatched responses show n/a.
    """
    output = {key: "n/a" for key in (
        "model", "output_limit", "reason", "input_tokens", "output_tokens",
        "reasoning_tokens", "response_status",
    )}
    output["diagnostic_match"] = "false"
    response_id = getattr(result, "provider_response_id", None)
    decision = getattr(result, "decision", None)
    route = getattr(decision, "route_name", None)
    router = getattr(orchestrator, "provider_router", None)
    if not isinstance(response_id, str) or not response_id or not isinstance(route, str) or not router:
        return output
    try:
        provider = router.resolve(route)
        lookup = getattr(provider, "response_diagnostics", None)
        data = lookup(response_id) if callable(lookup) else None
    except (KeyError, ValueError, AttributeError):
        return output
    if not isinstance(data, dict) or data.get("provider_response_id") != response_id:
        return output
    output["diagnostic_match"] = "true"
    model = data.get("requested_model")
    if isinstance(model, str) and re.fullmatch(r"gpt-[A-Za-z0-9_.-]{1,72}", model):
        output["model"] = model
    for dest, source in (
        ("output_limit", "requested_output_limit"),
        ("input_tokens", "input_tokens"),
        ("output_tokens", "output_tokens"),
        ("reasoning_tokens", "reasoning_tokens"),
    ):
        number = data.get(source)
        if type(number) is int and 0 <= number <= 10_000_000:
            output[dest] = str(number)
    if data.get("incomplete_reason") in ("max_output_tokens", "content_filter", "unknown"):
        output["reason"] = data["incomplete_reason"]
    if data.get("response_status") in ("completed", "incomplete", "failed", "cancelled"):
        output["response_status"] = data["response_status"]
    return output


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
        self._held_turn: int | None = None

    def new_turn(self, turn: int) -> None:
        if self._closed or turn <= self.current_turn or turn <= 0:
            return
        self._discard_held_result(reason="new_turn")
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

    async def _notify_test_hold_end(self, turn: int) -> None:
        try:
            await self.notify({"kind": "core_luna_cancel_hold_ended", "turn": turn})
        except Exception:
            # A test-only UI notification must never affect Core authority.
            pass

    def _discard_held_result(self, *, reason: str) -> None:
        """Finalize an opt-in hold before any result notification can cross turns.

        No async gap exists between invalidating this hold and changing the
        active turn. Normal (non-test) sessions never enter this method.
        """
        if self._held_turn is None:
            return
        held = self._held_turn
        self._held_turn = None
        # Clear the desktop test banner. This contains only a turn ID.
        asyncio.create_task(self._notify_test_hold_end(held))
        print(f"[Jarvis Luna Cancel Test] turn={held} | phase=stale_result_discarded "
              f"| reason={reason} | voice_delivered=false", flush=True)
        print(f"[Jarvis Luna Cancel Test] turn={held} | phase=test_summary "
              f"| outcome=PASS | reason={reason} | result_released=false", flush=True)

    async def cancel(self) -> None:
        self._discard_held_result(reason="sleep_or_cancel")
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
                self._held_turn = turn
                print(f"[Jarvis Luna Cancel Test] turn={turn} | phase=holding_result "
                      f"| seconds={self.result_hold_seconds:g} | authority=none", flush=True)
                # The renderer updates the test banner. On Windows, play a
                # *native* WAV rather than depending on an AudioContext resumed
                # from an unsolicited WebSocket event (which may remain suspended).
                silent_cue = os.environ.get("JARVIS_SILENT_TEST_CUES") == "1"
                native_cue = sys.platform == "win32"
                try:
                    await self.notify({"kind": "core_luna_cancel_hold", "turn": turn,
                                       "seconds": self.result_hold_seconds,
                                       "cue_route": "silent" if silent_cue else ("native_windows" if native_cue else "renderer")})
                except Exception:
                    print(f"[Jarvis Luna Cancel Test] turn={turn} | phase=cue_ui_unavailable", flush=True)
                if native_cue:
                    print(f"[Jarvis Luna Cancel Test] turn={turn} | phase=cue_playback | route=windows_default_audio | state=starting", flush=True)
                    try:
                        # Short bounded cue on the default Windows audio output;
                        # no event-loop blocking and no output-device assumptions.
                        cue_status = await asyncio.wait_for(
                            asyncio.to_thread(play_native_hold_cue), timeout=1.75)
                    except Exception:
                        cue_status = "playback_api_failed"
                    print(f"[Jarvis Luna Cancel Test] turn={turn} | phase=cue_playback | route=windows_default_audio | state={cue_status}", flush=True)
                    if cue_status not in {"playback_api_completed", "silenced_by_test_setting"} and self._held_turn == turn:
                        try:
                            await self.notify({"kind": "core_luna_cancel_cue_fallback", "turn": turn})
                        except Exception:
                            pass
                if self._closed or turn != self.current_turn or self._held_turn != turn:
                    return
                # The full eight seconds start AFTER the cue completes.
                print(f"[Jarvis Luna Cancel Test] turn={turn} | phase=interrupt_window_open | seconds={self.result_hold_seconds:g}", flush=True)
                await asyncio.sleep(self.result_hold_seconds)
                if self._closed or turn != self.current_turn or self._held_turn != turn:
                    if self._held_turn == turn:
                        self._discard_held_result(reason="stale_at_expiry")
                    return
                self._held_turn = None
                print(f"[Jarvis Luna Cancel Test] turn={turn} | phase=releasing_current_result", flush=True)
                print(f"[Jarvis Luna Cancel Test] turn={turn} | phase=test_summary "
                      "| outcome=NOT_TESTED | reason=hold_expired | result_released=true", flush=True)
                await self._notify_test_hold_end(turn)
            budget = _safe_core_budget_fields(self.orchestrator, result)
            print(f"[Jarvis Luna Budget] turn={turn} | phase=provider_terminal "
                  f"| diagnostic_match={budget['diagnostic_match']} | model={budget['model']} "
                  f"| output_limit={budget['output_limit']} | response_status={budget['response_status']} "
                  f"| incomplete_reason={budget['reason']} | input_tokens={budget['input_tokens']} "
                  f"| output_tokens={budget['output_tokens']} | reasoning_tokens={budget['reasoning_tokens']}", flush=True)
            if result.status is DelegationStatus.COMPLETED and result.text.strip():
                await self._result(turn, "completed", result.text.strip(), started,
                                   route=result.decision.route_name or "unknown")
            else:
                status = str(result.status.value)
                fields = _safe_core_failure_fields(getattr(result, "detail", None))
                # Status-only logs concealed HTTP 400/429/5xx and provider faults.
                # This metadata is all non-sensitive; raw detail is NOT logged.
                route_name = str(getattr(result.decision, "route_name", "") or "unknown")
                route_name = route_name if route_name in {"strong", "default", "primary", "luna"} else "redacted"
                print(f"[Jarvis Luna Diagnostic] turn={turn} | phase=core_failed "
                      f"| status={status} | route={route_name} "
                      f"| http_status={fields['http_status']} "
                      f"| error_type={fields['error_type']} "
                      f"| error_code={fields['error_code']} "
                      f"| error_param={fields['error_param']} "
                      f"| detail_class={fields['detail_class']} "
                      f"| response_id_present={bool(getattr(result, 'provider_response_id', None))} "
                      f"| partial_text_present={bool(str(getattr(result, 'text', '') or '').strip())}", flush=True)
                await self._result(turn, status,
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
