"""0.1.5.7: one turn-owned interface for browser and audited desktop app tools.

Mini chooses which tool to propose. Independent user evidence and executor
policy are checked in Core. The existing browser path remains untouched.
"""
from __future__ import annotations

import re

from apps.desktop_managed_browser import ManagedDesktopBrowserSession, ManagedBrowserOutcome
from core.common.ids import CorrelationContext
from core.tools import ToolRequest
from core.tools.desktop_apps import CoreDesktopAppGateway
from core.tools.gateway import ConfirmedUserAction


class UnifiedDesktopActionSession(ManagedDesktopBrowserSession):
    def __init__(self, *, app_launcher=None, universal_apps: bool=False, **kwargs):
        super().__init__(**kwargs)
        self.app_gateway = CoreDesktopAppGateway(launcher=app_launcher, dynamic=universal_apps)

    async def handle(self, *, turn: int, selected_tool: str, source: str,
                     binding: str, transcript: object, arguments: object = None) -> ManagedBrowserOutcome | None:
        if selected_tool != 'launch_app':
            return await super().handle(turn=turn, selected_tool=selected_tool,
                                        source=source, binding=binding,
                                        transcript=transcript, arguments=arguments)
        if type(turn) is not int or turn < 1 or turn != self.active_turn or turn in self.handled:
            return None
        self.handled.add(turn)
        bound = (source == 'typed' and binding == f'typed:{turn}') or (
            source == 'voice' and isinstance(binding, str) and
            re.fullmatch(r'item_[A-Za-z0-9_-]{1,120}', binding) is not None)
        if not bound or not isinstance(transcript, str) or not isinstance(arguments, dict):
            return ManagedBrowserOutcome('failed', 'I could not verify that application request.',
                                         'missing_independent_user_evidence')
        if set(arguments) != {'app'} or not isinstance(arguments.get('app'), str):
            return ManagedBrowserOutcome('failed', 'That application request is invalid.',
                                         'unapproved_application')
        trace = CorrelationContext.create()
        request = ToolRequest(trace, 'desktop_app', 'launch',
                              {'app': arguments['app']}, idempotency_key=f'local-turn-{turn}')
        outcome = await self.app_gateway.execute(request, evidence=ConfirmedUserAction(
            trace.turn_id, transcript, True, True))
        if outcome.status.value == 'succeeded':
            return ManagedBrowserOutcome('completed',
                                         outcome.output.get('user_message', 'Launch request sent.'),
                                         'handoff_not_window_verified')
        return ManagedBrowserOutcome('failed', outcome.error_message or 'I could not launch that application.',
                                     outcome.error_code or 'launch_failed')
