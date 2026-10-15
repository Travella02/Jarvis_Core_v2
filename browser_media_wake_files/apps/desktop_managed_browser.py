"""0.1.5.4 opt-in Core-authorized, turn-scoped managed browser session."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from core.common.ids import CorrelationContext
from core.tools import ToolRequest
from core.tools.gateway import ConfirmedUserAction
from core.tools.managed_browser import ManagedBrowserGateway, BrowserOperations, ALLOWED

@dataclass(frozen=True)
class ManagedBrowserOutcome:
    status: str
    text: str
    code: str

class ManagedDesktopBrowserSession:
    def __init__(self, *, browser: BrowserOperations|None=None, advanced:bool=False):
        self.gateway=ManagedBrowserGateway(browser, advanced=advanced)
        self.advanced=advanced
        self.active_turn=0
        self.handled:set[int]=set()

    def on_turn_started(self, turn:int)->None:
        if type(turn) is int and turn>self.active_turn:self.active_turn=turn
        if len(self.handled)>256:
            self.handled={t for t in self.handled if t>=self.active_turn-256}

    async def handle(self, *, turn:int, selected_tool:str, source:str,
                     binding:str, transcript:object, arguments:object=None) -> ManagedBrowserOutcome|None:
        if type(turn) is not int or turn<1 or turn!=self.active_turn or turn in self.handled:
            return None
        self.handled.add(turn)  # fail closed on duplicate calls even when malformed
        bound=(source=='typed' and binding==f'typed:{turn}') or (
              source=='voice' and isinstance(binding,str) and
              re.fullmatch(r'item_[A-Za-z0-9_-]{1,120}',binding) is not None)
        if selected_tool!='browser_action' or not bound or not isinstance(transcript,str) or not isinstance(arguments,dict):
            return ManagedBrowserOutcome('failed','I could not verify that browser request.',
                                         'missing_independent_user_evidence')
        intent=arguments.get('intent')
        if (intent not in ALLOWED or not isinstance(intent,str) or
                (not self.advanced and intent in {'select_tab','close_named_tab','play','pause','mute','unmute','volume'}) or
                not isinstance(arguments.get('site'),str)):
            return ManagedBrowserOutcome('failed','I do not support that browser operation yet.','unknown_operation')
        expected={'site','intent','query'} if intent=='search' else {'site','intent','value'} if intent=='volume' else {'site','intent'}
        cleaned={k:v for k,v in arguments.items() if not (k=='query' and intent!='search' and v in ('',None))}
        if set(cleaned)!=expected:
            return ManagedBrowserOutcome('failed','Those browser parameters are not authorized.','invalid_arguments')
        args={'site':cleaned['site']}
        if intent=='search':args['query']=cleaned['query']
        if intent=='volume':args['value']=cleaned['value']
        trace=CorrelationContext.create()
        request=ToolRequest(trace,'desktop_browser',intent,args,idempotency_key=f'local-turn-{turn}')
        result=await self.gateway.execute(request,evidence=ConfirmedUserAction(
            trace.turn_id,transcript,True,True))
        if result.status.value=='succeeded':
            return ManagedBrowserOutcome('completed',result.output.get('user_message','Browser action completed.'),'none')
        return ManagedBrowserOutcome('failed',result.error_message or 'I could not complete that browser action.',
                                     result.error_code or 'unknown_failure')

    async def close(self)->None:
        await self.gateway.close()
