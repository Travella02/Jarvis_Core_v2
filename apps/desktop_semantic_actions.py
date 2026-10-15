"""Turn-scoped opt-in semantic tool proposal coordinator; Core owns effects."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import re

from core.common.ids import CorrelationContext
from core.tools import ToolRequest
from core.tools.gateway import ConfirmedUserAction
from core.tools.semantic_browser import SemanticBrowserGateway, OPEN, SEARCH


@dataclass(frozen=True)
class SemanticActionOutcome:
    status: str
    text: str
    code: str


class SemanticDesktopActionSession:
    def __init__(self, *, launcher: Callable[[str],bool] | None = None):
        self.gateway = SemanticBrowserGateway(launch_browser=launcher)
        self.active_turn = 0
        self.handled: set[int] = set()

    def on_turn_started(self, turn: int) -> None:
        if type(turn) is int and turn > self.active_turn:
            self.active_turn = turn
        if len(self.handled) > 256:
            self.handled = {t for t in self.handled if t >= self.active_turn - 256}

    async def handle(self, *, turn: int, selected_tool: str, source: str,
                     binding: str, transcript: str, arguments: object = None) -> SemanticActionOutcome | None:
        if type(turn) is not int or turn < 1 or turn != self.active_turn or turn in self.handled:
            return None
        # Mark BEFORE checking authorization so a denied/ambiguous turn cannot
        # repeat with a revised model proposal (or a second WebSocket event).
        self.handled.add(turn)
        bound = (source == 'typed' and binding == f'typed:{turn}') or (
            source == 'voice' and re.fullmatch(r'item_[A-Za-z0-9_-]{1,120}', binding) is not None)
        if (selected_tool != 'browser_action' or not bound or not isinstance(transcript,str) or
                not isinstance(arguments,dict) or len(transcript) > 2000):
            return SemanticActionOutcome('failed','I could not verify that browser request.',
                                         'missing_independent_user_evidence')
        site = arguments.get('site')
        intent = arguments.get('intent')
        argset = {'site'}
        if intent == 'open':
            operation = OPEN
        elif intent == 'search':
            operation = SEARCH
            argset.add('query')
        else:
            return SemanticActionOutcome('failed','I could not verify that browser operation.','unknown_operation')
        # Some model tool serializers emit an optional empty search query for
        # homepage opens. Discard only that harmless empty value, never a URL.
        if intent == 'open' and arguments.get('query') in ('', None):
            arguments = {k:v for k,v in arguments.items() if k != 'query'}
        if set(arguments) != argset | {'intent'}:
            return SemanticActionOutcome('failed','I could not verify those browser arguments.','invalid_arguments')
        trace = CorrelationContext.create()
        request_args = {'site':site}
        if intent == 'search': request_args['query'] = arguments['query']
        req = ToolRequest(trace,'desktop_browser',operation,request_args,
                          idempotency_key=f'local-turn-{turn}')
        outcome = await self.gateway.execute(req,evidence=ConfirmedUserAction(
            trace.turn_id,transcript,confirmed=True,local_desktop=True))
        if outcome.status.value == 'succeeded':
            return SemanticActionOutcome('completed',outcome.output['user_message'],'none')
        return SemanticActionOutcome('failed',outcome.error_message or
                                     'That browser action is not authorized.',outcome.error_code or 'unknown_failure')
