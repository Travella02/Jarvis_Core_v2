"""0.1.5.2 opt-in Core browser action coordinator.

A Mini tool selection is not an authorization. We require independent same-turn
committed speech text (or submitted typed text), then the 0.1.5.1 gateway checks
one exact command against the site allowlist. Nothing arbitrary reaches Windows.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from collections.abc import Callable

from core.common.ids import CorrelationContext
from core.tools import ToolRequest
from core.tools.gateway import ConfirmedUserAction, CoreToolGateway


@dataclass(frozen=True)
class ActionOutcome:
    status: str
    text: str
    code: str


class DesktopActionSession:
    def __init__(self, *, launcher: Callable[[str], bool] | None = None):
        self.gateway = CoreToolGateway(launch_browser=launcher)
        self.active_turn = 0
        self.handled: set[int] = set()

    def on_turn_started(self, turn: int) -> None:
        if isinstance(turn, int) and not isinstance(turn, bool) and turn > self.active_turn:
            self.active_turn = turn
        # Limit session memory, while still blocking replays for recent turns.
        if len(self.handled) > 256:
            self.handled = {t for t in self.handled if t >= self.active_turn - 256}

    async def handle(self, *, turn: int, selected_tool: str, source: str,
                     binding: str, transcript: str) -> ActionOutcome | None:
        if not isinstance(turn, int) or isinstance(turn, bool) or turn < 1 or \
                turn != self.active_turn or turn in self.handled:
            return None  # Ignore duplicate/stale action proposals, no side effects.
        self.handled.add(turn)
        bound = (source == 'typed' and binding == f'typed:{turn}') or (
            source == 'voice' and re.fullmatch(r'item_[A-Za-z0-9_-]{1,120}', binding) is not None
        )
        if selected_tool != 'test_action' or not bound or not isinstance(transcript, str) or \
                not transcript.strip() or len(transcript) > 240:
            return ActionOutcome('failed', "I didn't open anything; I couldn't verify that request.",
                                 'missing_independent_user_evidence')
        trace = CorrelationContext.create()
        request = ToolRequest(trace, 'desktop_browser', 'open_approved_site',
                              {'site':'youtube'}, idempotency_key=trace.request_id)
        result = await self.gateway.execute(request, evidence=ConfirmedUserAction(
            trace.turn_id, transcript, confirmed=True, local_desktop=True))
        if result.status.value == 'succeeded':
            return ActionOutcome('completed', str(result.output['user_message']), 'none')
        return ActionOutcome('failed', result.error_message or
                             "I didn't open anything. This test only supports 'open YouTube'.",
                             result.error_code or 'unknown_failure')
