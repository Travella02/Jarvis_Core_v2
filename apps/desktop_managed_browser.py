"""0.1.5.4 opt-in Core-authorized, turn-scoped managed browser session."""
from __future__ import annotations

import re
import time
import asyncio
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
    spoken_result: bool = False

class ManagedDesktopBrowserSession:
    def __init__(self, *, browser: BrowserOperations|None=None, advanced:bool=False, launch_default=None, bridge_mode:bool=False, terra_navigator=None):
        self.gateway=ManagedBrowserGateway(browser, advanced=advanced, launch_default=launch_default, bridge_mode=bridge_mode)
        self.advanced=advanced
        self.bridge_mode=bridge_mode
        self.active_turn=0
        self.handled:set[int]=set()
        self._scroll_context: tuple[int,str,float,tuple[int,str]] | None = None
        self._terra_navigator = terra_navigator

    def on_turn_started(self, turn:int)->None:
        if type(turn) is int and turn>self.active_turn:self.active_turn=turn
        if len(self.handled)>256:
            self.handled={t for t in self.handled if t>=self.active_turn-256}

    async def handle(self, *, turn:int, selected_tool:str, source:str,
                     binding:str, transcript:object, arguments:object=None) -> ManagedBrowserOutcome|None:
        if type(turn) is not int or turn<1 or turn!=self.active_turn or turn in self.handled:
            return None
        self.handled.add(turn)  # fail closed on duplicate calls even when malformed
        # The Mini router may wrongly choose browser_action for an explicit
        # READ-ONLY request about the separately configured background browser.
        # Recover only from authenticated same-turn evidence, never model args.
        # This does not execute a model-selected browser command or click/type;
        # even if normal Terra execution is on, this recovery is preview-only.
        bound_nav = ((source == 'typed' and binding == f'typed:{turn}') or
                     (source == 'voice' and isinstance(binding,str) and
                      re.fullmatch(r'item_[A-Za-z0-9_-]{1,120}',binding) is not None))
        if selected_tool == 'browser_action' and bound_nav and isinstance(transcript,str) and self._terra_navigator is not None:
            from urllib.parse import urlsplit
            from core.tools.terra_navigation import confirmed_isolated_browser_inspection
            nav_env = self._terra_navigator.env
            mode = nav_env.get('JARVIS_TERRA_NAV_MODE','foreground').strip().lower()
            domain = (urlsplit(nav_env.get('JARVIS_TERRA_BACKGROUND_URL','')).hostname or '').lower()
            if mode == 'isolated_browser' and confirmed_isolated_browser_inspection(transcript,domain):
                print(f'[Jarvis Terra Route] turn={turn} | proposed=browser_action | resolved=navigate_app | read_only=True | evidence=current_turn',flush=True)
                output = await asyncio.to_thread(self._terra_navigator.run,transcript,
                    cancelled=lambda: self.active_turn != turn, read_only=True)
                print(f'[Jarvis Terra] turn={turn} | status={output.status} | code={output.code} | actions={output.actions} | authority=core',flush=True)
                return ManagedBrowserOutcome(output.status,output.message,output.code,None,output.spoken)
        if selected_tool == 'navigate_app':
            # An independent current-turn transcript authorizes the TASK, never
            # the model-supplied argument. Existing application only; no launch.
            bound_nav = ((source == 'typed' and binding == f'typed:{turn}') or
                         (source == 'voice' and isinstance(binding,str) and
                          re.fullmatch(r'item_[A-Za-z0-9_-]{1,120}',binding) is not None))
            if not bound_nav or not isinstance(transcript,str) or not isinstance(arguments,dict) or set(arguments) != {'task'}:
                return ManagedBrowserOutcome('failed','I could not verify that computer navigation request.','missing_independent_user_evidence')
            if self._terra_navigator is None:
                return ManagedBrowserOutcome('failed','Computer navigation is not enabled.','terra_disabled')
            output = await asyncio.to_thread(self._terra_navigator.run, transcript,
                cancelled=lambda: self.active_turn != turn)
            print(f'[Jarvis Terra] turn={turn} | status={output.status} | code={output.code} | actions={output.actions} | authority=core',flush=True)
            return ManagedBrowserOutcome(output.status, output.message, output.code,
                {'category':'desktop','intent':'navigate'} if output.status=='completed' and output.actions else None,
                output.spoken)
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
        # A user-described video title is an entity reference, not a new URL.
        # Mini sometimes proposes PLAY or generic OPEN for "play the X video",
        # or appends stale search terms to select_match.query. Repair only an
        # ALREADY PROPOSED browser action using the independently committed
        # current-turn transcript. Core later rechecks the intent, live active
        # search tab, grounded result labels, and destination before navigation.
        # This is not a phrase-to-tool fast path: if Mini chose conversation or
        # an unrelated action, nothing is executed.
        if self.advanced and self.bridge_mode and intent in ('open', 'play', 'select_match'):
            from core.tools.managed_browser import confirmed_video_title_request
            spoken_title = confirmed_video_title_request(transcript)
            allowed_site = (isinstance(arguments.get('site'), str) and (
                arguments['site'] in ('current', 'youtube.com') or
                (intent in ('open', 'play') and len(arguments['site']) <= 140 and
                 not any(c in arguments['site'] for c in '/:?#@') and
                 normalize_host(arguments['site']) is None)))
            shape_ok = (set(arguments) == {'site','intent'} if intent in ('open', 'play')
                        else set(arguments) == {'site','intent','query'})
            model_query_ok = True
            if intent == 'select_match':
                proposed = arguments.get('query')
                if not isinstance(proposed, str):
                    model_query_ok = False
                else:
                    # A model's extra search-context terms are never sent to the
                    # matcher. Require independent overlap with spoken content,
                    # or refuse a wholly invented/mismatched title.
                    from core.tools.default_browser_bridge import DefaultBrowserBridgeAdapter
                    spoken_terms = set(DefaultBrowserBridgeAdapter._video_match_tokens(spoken_title or ''))
                    proposed_terms = set(DefaultBrowserBridgeAdapter._video_match_tokens(proposed))
                    model_query_ok = (bool(proposed_terms) and
                                      len(spoken_terms & proposed_terms) >= min(2, len(spoken_terms)))
            if spoken_title and allowed_site and shape_ok and model_query_ok:
                original_intent = intent
                arguments = {'site':'current', 'intent':'select_match', 'query':spoken_title}
                intent = 'select_match'
                print(f'[Jarvis Browser Title Route] proposed={original_intent} | resolved=select_match | evidence=current_turn | query_source=confirmed_speech',flush=True)

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
                (not self.advanced and intent in {'select_tab','close_named_tab','play','pause','mute','unmute','volume','select_result','select_match','inspect_page','fullscreen','exit_fullscreen','scroll','open_managed'}) or
                (self.bridge_mode and intent == 'open_managed') or
                not isinstance(arguments.get('site'),str)):
            return ManagedBrowserOutcome('failed','I do not support that browser operation yet.','unknown_operation')
        # Navigation potentially opens/focuses a browser window. Protect a
        # foreground game even when Mini selected the legacy browser tool.
        # Read-only inspection and passive media toggles do not require focus.
        if intent in {'open','search','open_managed','select_result','select_match',
                      'close_tab','next_tab','select_tab','close_named_tab'}:
            from core.tools.foreground_safety import protect_existing_desktop_action
            focus_reason=protect_existing_desktop_action()
            if focus_reason:
                return ManagedBrowserOutcome('failed',
                    'The current foreground activity is protected; I did not switch browser windows.',
                    focus_reason)
        expected={'site','intent','query'} if intent in ('search','select_match') else {'site','intent','value'} if intent in ('volume','select_result') else {'site','intent','direction'} if intent=='scroll' else {'site','intent'}
        cleaned={k:v for k,v in arguments.items() if not (k=='query' and intent!='search' and v in ('',None))}
        if set(cleaned)!=expected:
            return ManagedBrowserOutcome('failed','Those browser parameters are not authorized.','invalid_arguments')
        args={'site':cleaned['site']}
        if intent in ('search','select_match'):args['query']=cleaned['query']
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
                                         'none', verified, bool(result.output.get('spoken_result')))
        return ManagedBrowserOutcome('failed',result.error_message or 'I could not complete that browser action.',
                                     result.error_code or 'unknown_failure')

    async def close(self)->None:
        await self.gateway.close()
