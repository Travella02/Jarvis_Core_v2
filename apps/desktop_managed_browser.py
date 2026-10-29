"""0.1.5.4 opt-in Core-authorized, turn-scoped managed browser session."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

from core.common.ids import CorrelationContext
from core.tools import ToolRequest
from core.tools.gateway import ConfirmedUserAction
from core.tools.managed_browser import ManagedBrowserGateway, BrowserOperations, ALLOWED, normalize_host

@dataclass(frozen=True)
class ManagedBrowserOutcome:
    status: str
    text: str
    code: str
    # Core-verified operation metadata; advisory context, NEVER authority.
    action_context: dict[str, str] | None = None

class ManagedDesktopBrowserSession:
    def __init__(self, *, browser: BrowserOperations|None=None, advanced:bool=False, launch_default=None, bridge_mode:bool=False):
        self.gateway=ManagedBrowserGateway(browser, advanced=advanced, launch_default=launch_default, bridge_mode=bridge_mode)
        self.advanced=advanced
        self.bridge_mode=bridge_mode
        self.active_turn=0
        self.handled:set[int]=set()
        self._scroll_context: tuple[int,str,float,tuple[int,str]] | None = None

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
        # Mini can choose generic open/play for a contextual ordinal follow-up
        # such as "let's watch the first one". Translate ONLY an existing model
        # browser proposal, ONLY using the independently committed transcript.
        # There is no keyword fast-path that initiates an action by itself.
        # The actual select_result gateway still requires a verified current
        # YouTube search page and grounded video link before navigation.
        if (self.advanced and self.bridge_mode and intent in ('open', 'play')
                and set(arguments) == {'site', 'intent'}
                and isinstance(arguments.get('site'), str)
                and (arguments['site'] in ('current', 'youtube.com') or
                     (len(arguments['site']) <= 70 and
                      not any(c in arguments['site'] for c in '/:?#@') and
                      normalize_host(arguments['site']) is None))):
            # The model's proposed site/ordinal can be wrong. Only the
            # confirmed utterance supplies the ordinal. The gateway later
            # verifies the live active search tab and grounded video URL.
            from core.tools.managed_browser import confirmed_result_selection_index
            ordinal = confirmed_result_selection_index(transcript)
            if ordinal is not None:
                arguments = {'site': 'current', 'intent': 'select_result', 'value': ordinal}
                intent = 'select_result'
        # Reconcile a mistaken "open YouTube" proposal to PAUSE only when the
        # current user utterance directly and unambiguously requests that media
        # action. Core then independently checks a fresh active watch-page
        # snapshot and the extension verifies the player. No new tool is fired
        # when Mini proposed direct conversation or an unrelated operation.
        if (self.advanced and self.bridge_mode and intent in ('open','pause')
                and arguments.get('site') in ('youtube.com','current')
                and set(arguments)=={'site','intent'}):
            from core.tools.managed_browser import confirmed_youtube_pause_request
            if confirmed_youtube_pause_request(transcript):
                arguments={'site':'current','intent':'pause'}
                intent='pause'

        # Some model proposals call "jump to the bottom" a relative DOWN
        # scroll or a generic OPEN. Reconcile ONLY an explicit, single endpoint
        # instruction from the independently confirmed user speech. Core still
        # checks scope and the extension verifies real movement.
        if (self.advanced and self.bridge_mode and intent in ('open','scroll')
                and arguments.get('site') in ('current','youtube.com')
                and (set(arguments)=={'site','intent'} if intent=='open'
                     else set(arguments)=={'site','intent','direction'})):
            from core.tools.managed_browser import trusted_intent
            endpoint=next((d for d in ('top','bottom')
                           if trusted_intent(transcript,'scroll','current',direction=d)),None)
            if endpoint:
                arguments={'site':'current','intent':'scroll','direction':endpoint}
                intent='scroll'

        # scroll only when Mini has independently selected scroll and a fresh
        # extension snapshot confirms the SAME active tab and URL.
        scroll_continuation=False
        previous=self._scroll_context
        if (self.advanced and self.bridge_mode and intent=='scroll'
                and previous is not None and turn==previous[0]+1
                and time.monotonic()-previous[2]<=15
                and re.fullmatch(r'\s*(?:jarvis[, ]+)?(?:please\s+)?keep\s+going(?:\s+please)?[.!?]*\s*',transcript,re.I)
                and arguments.get('site')=='current'
                and set(arguments)=={'site','intent','direction'}):
            verifier=getattr(self.gateway.browser,'verify_scroll_identity',None)
            if callable(verifier) and await verifier(previous[3]):
                scroll_continuation=True
                arguments={'site':'current','intent':'scroll','direction':previous[1]}

        # Mini occasionally encodes a request to RETURN to a site AND SEARCH it
        # as select_tab/open with a query. Interpret that *single proposed tool*
        # as search only when Mini supplied a query AND the independent user's
        # current-turn speech explicitly requested a search for those terms.
        # No query is inferred, no second effect is executed, and the browser
        # gateway still enforces host, transcript, permissions and idempotency.
        if (intent in {'select_tab', 'open'} and isinstance(arguments.get('site'), str)
                and isinstance(arguments.get('query'), str)
                and 2 <= len(arguments['query'].strip()) <= 160):
            from core.tools.managed_browser import confirmed_site_search_query
            if confirmed_site_search_query(transcript, arguments['site'], arguments['query']):
                arguments = {'site': arguments['site'], 'intent': 'search',
                             'query': arguments['query']}
                intent = 'search'
        if (intent not in ALLOWED or not isinstance(intent,str) or
                (not self.advanced and intent in {'select_tab','close_named_tab','play','pause','mute','unmute','volume','select_result','fullscreen','exit_fullscreen','scroll','open_managed'}) or
                (self.bridge_mode and intent == 'open_managed') or
                not isinstance(arguments.get('site'),str)):
            return ManagedBrowserOutcome('failed','I do not support that browser operation yet.','unknown_operation')
        expected={'site','intent','query'} if intent=='search' else {'site','intent','value'} if intent in ('volume','select_result') else {'site','intent','direction'} if intent=='scroll' else {'site','intent'}
        cleaned={k:v for k,v in arguments.items() if not (k=='query' and intent!='search' and v in ('',None))}
        if set(cleaned)!=expected:
            return ManagedBrowserOutcome('failed','Those browser parameters are not authorized.','invalid_arguments')
        args={'site':cleaned['site']}
        if intent=='search':args['query']=cleaned['query']
        if intent in ('volume','select_result'):args['value']=cleaned['value']
        if intent=='scroll':args['direction']=cleaned['direction']
        trace=CorrelationContext.create()
        request=ToolRequest(trace,'desktop_browser',intent,args,idempotency_key=f'local-turn-{turn}')
        result=await self.gateway.execute(request,evidence=ConfirmedUserAction(
            trace.turn_id,transcript,True,True),scroll_continuation=scroll_continuation)
        if intent=='scroll' and result.status.value=='succeeded':
            identity=getattr(self.gateway.browser,'last_scroll_identity',None)
            self._scroll_context=(turn,cleaned['direction'] if not scroll_continuation else arguments['direction'],time.monotonic(),identity) if identity else None
        else:
            self._scroll_context=None
        if result.status.value=='succeeded':
            verified = {'category': 'browser', 'intent': intent}
            if intent == 'scroll':
                verified['direction'] = str(args['direction'])
            return ManagedBrowserOutcome('completed',result.output.get('user_message','Browser action completed.'),
                                         'none', verified)
        return ManagedBrowserOutcome('failed',result.error_message or 'I could not complete that browser action.',
                                     result.error_code or 'unknown_failure')

    async def close(self)->None:
        await self.gateway.close()
