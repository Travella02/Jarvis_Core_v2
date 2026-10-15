"""Experimental Core-owned semantic browser action authorization (0.1.5.3).

The model proposes a *typed* browser action. It never chooses a URL or executes.
Core checks independent current-turn transcript evidence, approved capability,
negation/conditional/quoted/compound guards and idempotency before any effect.
This is deliberately a conservative capability, not a general desktop executor.
"""
from __future__ import annotations

import asyncio
import re
import webbrowser
from urllib.parse import quote_plus

from core.tools import ToolRequest, ToolResult, ToolResultStatus
from core.tools.gateway import APPROVED_SITES, ConfirmedUserAction, BrowserLauncher

CAPABILITY = 'desktop_browser'
OPEN = 'open_approved_site'
SEARCH = 'search_youtube'
ALLOWED_OPERATIONS = frozenset((OPEN, SEARCH))

# Safety checks are NOT a dictionary of permitted phrasings. Mini interprets
# the language. These checks independently veto ambiguous/untrusted instructions.
_SITE = re.compile(r'(?<![\w])(?:youtube(?:\.com)?|you[ -]?tube)(?![\w])', re.I)
_ACTION = re.compile(r'\b(?:open|launch|visit|navigate|browse|pull\s+up|pulling\s+up|bring\s+up|bringing\s+up|go\s+to|take\s+me\s+to|show\s+me|head\s+(?:over\s+)?to|bring\s+me\s+to|load|hop\s+(?:on|over)\s+to|find|search|look\s+up)\b', re.I)
_SEARCH = re.compile(r'\b(?:find|search|look\s+up|video|clip|tutorial)\b', re.I)
_NEGATED = re.compile(r"\b(?:don['’]?t|do\s+not|never|not\s+to|no\s+need\s+to|stop|avoid|without|refrain\s+from|wouldn['’]?t|shouldn['’]?t|cancel)\b", re.I)
_NON_REQUEST = re.compile(r'(?:^\s*(?:how\s+(?:do|to|would|can)|why\s+(?:do|would|did|should))\b|\b(?:explain|teach|describe)\s+(?:me\s+)?how\s+to\b|\b(?:what\s+if|hypothetic(?:al|ally)|pretend|imagine|someone\s+said|somebody\s+said|they\s+said|quoted?|example\s+of|definition\s+of|meaning\s+of|remind\s+me\s+to|later|tomorrow|next\s+week|if\s+(?:you|i|we|it)|unless|after\s+i|when\s+i)\b)', re.I)
_SECOND_ACTION = re.compile(r'\b(?:send\s+(?:an?\s+)?(?:email|message)|delete\s+(?:my|the|a)\s+\w+|buy\s+\w+|run\s+(?:my|the)\s+(?:code|script)|download\s+\w+|post\s+(?:it|this)|log\s+in|sign\s+in)\b', re.I)
_OTHER_SITE = re.compile(r'\b(?:google|gmail|facebook|reddit|netflix|tiktok|spotify|instagram|twitter)\b', re.I)
_URL = re.compile(r'(?:https?://|www\.)', re.I)


def _trusted_intent(transcript: str, operation: str) -> bool:
    if not isinstance(transcript, str) or not (1 <= len(transcript) <= 2000):
        return False
    text = ' '.join(transcript.split())
    # Polite "I would appreciate it if you could ..." is a genuine request,
    # unlike an actual conditional "if you can, ...". Keep the latter blocked.
    safety_text = re.sub(r'\bappreciate\s+it\s+if\s+you\s+(?:could|would|can)\b',
                         'appreciate it please',text,flags=re.I)
    if not _SITE.search(text) or not _ACTION.search(text):
        return False
    if any(check.search(safety_text) for check in (_NEGATED, _NON_REQUEST, _SECOND_ACTION, _OTHER_SITE, _URL)):
        return False
    # A YouTube search requires independent mention of searching/seeing video;
    # Core will not silently turn an explicit "open YouTube" into a different task.
    if operation == SEARCH and not _SEARCH.search(text):
        return False
    return True


class SemanticBrowserGateway:
    def __init__(self, *, launch_browser: BrowserLauncher | None = None) -> None:
        self._launch = launch_browser or webbrowser.open_new_tab
        self._lock = asyncio.Lock()
        self._replays: dict[tuple[str, str], tuple[str, ToolResult]] = {}

    async def execute(self, request: ToolRequest, *, evidence: ConfirmedUserAction | None) -> ToolResult:
        def result(status: ToolResultStatus, code: str | None = None, message: str | None = None,
                   output: dict | None = None) -> ToolResult:
            return ToolResult(trace=request.trace, tool_name=request.tool_name, operation=request.operation,
                              status=status, output=output or {}, provider_call_id=request.provider_call_id,
                              error_code=code, error_message=message)

        if request.tool_name != CAPABILITY or request.operation not in ALLOWED_OPERATIONS:
            return result(ToolResultStatus.DENIED, 'unknown_capability')
        site = request.arguments.get('site')
        if not isinstance(site, str) or site != 'youtube' or site not in APPROVED_SITES:
            return result(ToolResultStatus.DENIED, 'unapproved_destination', 'That destination is not approved yet.')
        query = request.arguments.get('query', '')
        if request.operation == OPEN:
            if set(request.arguments) != {'site'}:
                return result(ToolResultStatus.DENIED, 'invalid_arguments')
            url = APPROVED_SITES[site]
        else:
            if set(request.arguments) != {'site','query'} or not isinstance(query, str) or not (2 <= len(query.strip()) <= 160):
                return result(ToolResultStatus.DENIED, 'invalid_search_query')
            if any(c in query for c in ('\n','\r','\0')):
                return result(ToolResultStatus.DENIED, 'invalid_search_query')
            url = APPROVED_SITES['youtube'] + 'results?search_query=' + quote_plus(query.strip())
        if (evidence is None or not evidence.confirmed or not evidence.local_desktop or
                not request.trace.turn_id or request.trace.turn_id != evidence.turn_id):
            return result(ToolResultStatus.DENIED, 'missing_confirmed_user_turn')
        if not _trusted_intent(evidence.transcript, request.operation):
            return result(ToolResultStatus.DENIED, 'unverified_user_intent',
                          'I could not verify an immediate, approved browser request. Nothing opened.')
        key = (evidence.turn_id, request.idempotency_key or request.trace.request_id)
        fingerprint = repr((request.tool_name, request.operation, site, query))
        async with self._lock:
            cached = self._replays.get(key)
            if cached is not None:
                if cached[0] != fingerprint:
                    return result(ToolResultStatus.DENIED, 'replay_key_conflict')
                return cached[1]
            try:
                ok = self._launch(url) is True
            except Exception:
                ok = False
            outcome = (result(ToolResultStatus.SUCCEEDED, output={
                'browser_launch_accepted':True, 'page_loaded_verified':False, 'site':'youtube',
                'operation':request.operation, 'url':url,
                'user_message':'I sent your YouTube request to the default browser.'})
                if ok else result(ToolResultStatus.FAILED,'browser_launch_failed',
                                  'The default browser did not accept the request.'))
            self._replays[key] = (fingerprint,outcome)
            return outcome
