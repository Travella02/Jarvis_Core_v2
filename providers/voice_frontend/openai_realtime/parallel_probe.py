"""Repair6 instrumentation: read-only Luna shadow while Realtime routes.

This is NOT an action executor and must NEVER publish an answer, alter history,
store memory, or call Core tool handlers. It measures whether early transcripts
arrive in time to make parallel intelligence worthwhile. Strictly opt-in.
"""
from __future__ import annotations

import asyncio
from time import monotonic
from typing import Any

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.intelligence import IntelligenceContext, IntelligenceEventType, ReasoningPolicy


class ParallelShadowProbe:
    def __init__(self, provider: Any, *, deadline_seconds: float = 3.0) -> None:
        self.provider = provider
        self.deadline_seconds = deadline_seconds
        self._turn = 0
        self._task: asyncio.Task[None] | None = None
        self._token: CancellationToken | None = None
        self._route_decided: set[int] = set()
        self._closed = False

    def on_transcript(self, turn: int, text: str) -> None:
        text = text.strip()
        if self._closed or turn <= 0 or not text or turn in self._route_decided:
            if turn in self._route_decided:
                print(f"[Jarvis Parallel] turn={turn} | candidate=luna | status=transcript_after_route", flush=True)
            return
        if turn <= self._turn:
            return  # duplicated ASR event or stale turn
        self._cancel_current("new_turn")
        self._turn = turn
        self._token = CancellationToken()
        self._task = asyncio.create_task(self._run(turn, text, self._token), name=f"parallel-luna-shadow-{turn}")

    def on_route(self, turn: int, route: str) -> None:
        if turn <= 0:
            return
        self._route_decided.add(turn)
        if len(self._route_decided) > 128:
            self._route_decided = set(sorted(self._route_decided)[-64:])
        if turn == self._turn:
            # Shadow is never reused: a separate, authoritative Core path owns
            # validated results. Stop spending as soon as the route is known.
            self._cancel_current(f"route_{route}")

    def _cancel_current(self, reason: str) -> None:
        if self._token is not None:
            self._token.cancel(reason)
        if self._task is not None and not self._task.done():
            self._task.cancel()

    async def _run(self, turn: int, transcript: str, token: CancellationToken) -> None:
        started = monotonic()
        first_ms: int | None = None
        text_chars = 0
        status = "completed"
        try:
            # Minimal, stateless context intentionally avoids side effects and
            # sharing mutable Conversation Core history. No tools are provided.
            context = IntelligenceContext(
                trace=CorrelationContext.create(),
                messages=(
                    {"role": "system", "content": "Answer the user's question only. Do not call tools, take actions, or claim that actions occurred. Be concise."},
                    {"role": "user", "content": transcript},
                ),
                metadata={"input_channel": "parallel_shadow_probe"},
            )
            async def collect() -> None:
                nonlocal first_ms, text_chars, status
                async for event in self.provider.stream_response(
                    context, (), ReasoningPolicy(level="none", allow_escalation=False), token
                ):
                    if token.is_cancelled:
                        status = "cancelled"
                        break
                    if event.event_type is IntelligenceEventType.TEXT_DELTA and event.text_delta:
                        if first_ms is None:
                            first_ms = round((monotonic() - started) * 1000)
                        text_chars += len(event.text_delta)
                    elif event.event_type in {IntelligenceEventType.ERROR, IntelligenceEventType.DEGRADED}:
                        status = "provider_error"
                        break
            await asyncio.wait_for(collect(), timeout=self.deadline_seconds)
        except asyncio.CancelledError:
            status = "cancelled"
        except TimeoutError:
            status = "timeout"
        except Exception as exc:
            status = f"error_{type(exc).__name__}"
        finally:
            print(
                f"[Jarvis Parallel] turn={turn} | candidate=luna | status={status} | "
                f"first_token_ms={first_ms if first_ms is not None else 'n/a'} | "
                f"elapsed_ms={round((monotonic() - started) * 1000)} | text_chars={text_chars}",
                flush=True,
            )

    async def close(self) -> None:
        self._closed = True
        self._cancel_current("closed")
        if self._task is not None:
            await asyncio.gather(self._task, return_exceptions=True)
        if hasattr(self.provider, "close"):
            await self.provider.close()
