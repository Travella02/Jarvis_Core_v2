"""Repair1 regression: Mini desktop tool guidance + bounded joined-word STT repair."""
import unittest
from pathlib import Path

from core.tools.managed_browser import trusted_intent, _normalize_joined_browser_stt


class Repair1RoutingTests(unittest.TestCase):
    def test_realtime_mini_desktop_instructions_include_verified_select_result(self):
        src = (Path(__file__).resolve().parents[2] / 'apps/desktop/ui/src/App.tsx').read_text(encoding='utf8')
        self.assertIn('choose browser_action with intent=select_result, site=current', src)
        self.assertIn('must NOT be treated as direct conversation', src)
        self.assertNotIn('If user requests playing first search result, do not claim it is supported', src)
        self.assertIn('use intent=play ONLY to control a video already open', src)

    def test_normalizer_is_bounded_to_joined_browser_verb_site(self):
        self.assertEqual(_normalize_joined_browser_stt('Jervis OpenYouTube'), 'Jervis Open YouTube')
        self.assertEqual(_normalize_joined_browser_stt('searchGoogle for maps'), 'search Google for maps')
        self.assertEqual(_normalize_joined_browser_stt('DoNotOpenYouTube'), 'DoNotOpenYouTube')
        self.assertEqual(_normalize_joined_browser_stt('SuperOpenYouTubeX'), 'SuperOpenYouTubeX')
        self.assertEqual(_normalize_joined_browser_stt('Please open Notepad'), 'Please open Notepad')

    def test_joined_stt_open_respects_core_verifier(self):
        self.assertTrue(trusted_intent('Jervis OpenYouTube', 'open', 'youtube.com'))
        self.assertTrue(trusted_intent('Jarvis, OpenGoogle', 'open', 'google.com'))
        self.assertFalse(trusted_intent("Don't OpenYouTube", 'open', 'youtube.com'))
        self.assertFalse(trusted_intent('What if you OpenYouTube?', 'open', 'youtube.com'))
        self.assertFalse(trusted_intent('OpenYouTube and open Google', 'open', 'youtube.com'))
        self.assertFalse(trusted_intent('OpenYouTube', 'open', 'google.com'))

    def test_joined_stt_does_not_invent_search_topic_or_operation(self):
        self.assertFalse(trusted_intent('OpenYouTube', 'search', 'youtube.com', query='Sidemen'))
        self.assertTrue(trusted_intent('SearchYouTube for Sidemen', 'search', 'youtube.com', query='Sidemen'))
        self.assertFalse(trusted_intent('SearchYouTube for Sidemen', 'search', 'google.com', query='Sidemen'))
        self.assertFalse(trusted_intent('Do not SearchYouTube for Sidemen', 'search', 'youtube.com', query='Sidemen'))

    def test_verified_video_selection_not_weakened(self):
        self.assertTrue(trusted_intent('Play the first video','select_result','current', value=1))
        self.assertFalse(trusted_intent('Play the first video','select_result','current', value=2))
        self.assertFalse(trusted_intent("Don't play the first video",'select_result','current', value=1))
        self.assertFalse(trusted_intent('Play the first video and send an email','select_result','current', value=1))


if __name__ == '__main__': unittest.main()
