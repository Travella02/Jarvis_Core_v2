"""Semantic action alpha: no real browser/network/model/audio use."""
from __future__ import annotations

import asyncio
from pathlib import Path
import unittest
from urllib.parse import parse_qs, urlsplit

from apps.desktop_semantic_actions import SemanticDesktopActionSession
from core.common.ids import CorrelationContext
from core.tools import ToolRequest, ToolResultStatus
from core.tools.gateway import ConfirmedUserAction
from core.tools.semantic_browser import SemanticBrowserGateway, _trusted_intent

ROOT=Path(__file__).resolve().parents[2]


class SemanticActionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.urls=[]
        self.session=SemanticDesktopActionSession(launcher=lambda u: self.urls.append(u) or True)

    async def call(self, text: str, *, intent='open', query=None, site='youtube', source='voice',
                   binding=None, tool='browser_action', turn=None, params=None):
        if turn is None:
            self.session.on_turn_started(self.session.active_turn+1)
            turn=self.session.active_turn
        if binding is None:
            binding='typed:'+str(turn) if source=='typed' else 'item_voice'+str(turn)
        proposal={'site':site,'intent':intent}
        if query is not None: proposal['query']=query
        if params is not None: proposal=params
        return await self.session.handle(turn=turn,selected_tool=tool,source=source,
                                         binding=binding,transcript=text,arguments=proposal)

    async def test_natural_long_and_indirect_requests_are_not_full_phrase_matches(self):
        natural=(
            'Jarvis open YouTube.',
            'Thank you so much for explaining that. Could you please go ahead and open YouTube for me now?',
            'Hey, are you able to pull up YouTube for me?',
            'That was fantastic, Jarvis! Would you mind bringing up YouTube?',
            'I would really appreciate it if you could navigate to YouTube for me.',
            'Can you take me to YouTube, please?',
            'Sure, let us head over to YouTube now.',
        )
        for text in natural:
            got=await self.call(text)
            self.assertEqual(got.status,'completed',text)
        self.assertEqual(self.urls,['https://www.youtube.com/']*len(natural))

    async def test_search_is_only_encoded_youtube_results_and_contextual(self):
        got=await self.call('Thank you for that explanation, Jarvis. Can you open YouTube and find me a video about it?',
                           intent='search',query='how black holes form & star collapse')
        self.assertEqual(got.status,'completed')
        parsed=urlsplit(self.urls[0]);self.assertEqual(parsed.netloc,'www.youtube.com')
        self.assertEqual(parsed.path,'/results')
        self.assertEqual(parse_qs(parsed.query)['search_query'],['how black holes form & star collapse'])
        follow=await self.call('Can you search YouTube for how to cook rice?', intent='search', query='how to cook rice')
        self.assertEqual(follow.status,'completed')

    async def test_unapproved_unsupported_and_ambiguous_denied(self):
        texts=(
            "Don't open YouTube",'Please explain how to open YouTube',
            'I said open YouTube, but do not do that', 'If you get a chance, open YouTube',
            'Can you open YouTube tomorrow?', 'Someone said open YouTube',
            'Open YouTube and send an email', 'Open YouTube and Google',
            'Pretend to open YouTube', 'How would you open YouTube?',
            'Open https://youtube.com/watch?v=abc', 'Open Google instead',
            'What is the meaning of opening YouTube?',
        )
        for phrase in texts:
            got=await self.call(phrase)
            self.assertEqual(got.status,'failed',phrase)
        for site in ('google','other','https://youtube.com'):
            self.assertEqual((await self.call('open YouTube',site=site)).status,'failed')
        for params in ({'site':'youtube','intent':'open','url':'https://attacker.example'},
                       {'site':'youtube','intent':'search','query':'abc','url':'https://attacker.example'},
                       {'site':'youtube','intent':'delete'},
                       {'site':'youtube','intent':'search','query':''}):
            self.assertEqual((await self.call('Search YouTube for videos',params=params)).status,'failed')
        self.assertFalse(self.urls)

    async def test_model_call_without_exact_current_transcript_binding_denied(self):
        for options in ({'source':'voice','binding':''}, {'source':'typed','binding':'typed:999'},
                        {'tool':'test_action'}, {'source':'voice','binding':'item_!bad'}):
            self.assertEqual((await self.call('open YouTube',**options)).status,'failed')
        self.assertFalse(self.urls)
        self.session.on_turn_started(10)
        self.assertIsNone(await self.call('open YouTube',turn=9))

    async def test_duplicates_and_new_turn_win(self):
        self.session.on_turn_started(1)
        args=dict(turn=1,selected_tool='browser_action',source='voice',binding='item_abc',
                  transcript='open YouTube', arguments={'site':'youtube','intent':'open'})
        a,b=await asyncio.gather(self.session.handle(**args),self.session.handle(**args))
        self.assertEqual(sum(x is not None for x in (a,b)),1)
        self.assertEqual(len(self.urls),1)
        self.session.on_turn_started(2)
        self.assertIsNone(await self.session.handle(**args))

    async def test_launcher_failure_is_not_success(self):
        session=SemanticDesktopActionSession(launcher=lambda _:False)
        session.on_turn_started(1)
        got=await session.handle(turn=1,selected_tool='browser_action',source='typed',binding='typed:1',
                                 transcript='open YouTube',arguments={'site':'youtube','intent':'open'})
        self.assertEqual(got.code,'browser_launch_failed')
        self.assertEqual(got.status,'failed')

    async def test_core_requires_separate_confirmation_and_turn_id(self):
        gateway=SemanticBrowserGateway(launch_browser=lambda u:self.urls.append(u) or True)
        trace=CorrelationContext.create()
        proposal=ToolRequest(trace,'desktop_browser','open_approved_site',{'site':'youtube'})
        self.assertEqual((await gateway.execute(proposal,evidence=None)).status,ToolResultStatus.DENIED)
        wrong=ConfirmedUserAction('different','open YouTube',True,True)
        self.assertEqual((await gateway.execute(proposal,evidence=wrong)).status,ToolResultStatus.DENIED)
        self.assertFalse(self.urls)


class ContractTests(unittest.TestCase):
    def test_mode_is_opt_in_and_separate_from_accepted_voice(self):
        s=(ROOT/'scripts/realtime_ab.py').read_text(encoding='utf8')
        self.assertIn('mini-overlap-luna-trim-guided-semantic',s)
        self.assertIn('JARVIS_SEMANTIC_ACTIONS_PROBE',s)
        source=(ROOT/'apps/desktop_alpha.py').read_text(encoding='utf8')
        self.assertIn('SemanticDesktopActionSession',source)
        self.assertIn('semantic_actions_probe',source)
        self.assertIn("'browser_action'",source)
        self.assertNotIn('webbrowser.open',source)

    def test_model_arguments_are_sent_to_core_but_never_direct_browser(self):
        ui=(ROOT/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf8')
        self.assertIn('proposal = raw',ui)
        self.assertIn('arguments:pending.proposal || null',ui)
        self.assertIn('semanticActionsRef.current',ui)
        self.assertNotIn('window.open(',ui)

    def test_conversation_direct_branch_preserved(self):
        ui=(ROOT/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf8')
        self.assertIn("overlapDecisionRef.current === 'direct'",ui)
        self.assertIn('settlePendingOverlapDirect();',ui)
        self.assertIn("max_output_tokens:1024,tools:[],tool_choice:'none'",ui)
        # Action classification shares the existing decision; no separate API call.
        self.assertIn('semanticActionsRef.current ? tool ===',ui)

if __name__=='__main__':unittest.main()
